from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from places.models import Place

from .emails import send_claim_invitation
from .forms import ClaimRequestForm, ServiceOfferingForm
from .models import ServiceOffering
from .tokens import make_claim_token, read_claim_token


AUTH_BACKEND = 'django.contrib.auth.backends.ModelBackend'


def claim_offer(request):
    total_places = Place.objects.filter(is_active=True).count()
    claimed_places = Place.objects.filter(is_active=True, owner__isnull=False).count()
    total_services = ServiceOffering.objects.filter(is_active=True).count()

    return render(request, 'claim/offer.html', {
        'total_places': total_places,
        'claimed_places': claimed_places,
        'unclaimed_places': max(total_places - claimed_places, 0),
        'total_services': total_services,
    })


def start_claim(request, place_id):
    place = get_object_or_404(Place, pk=place_id, is_active=True)

    if place.owner_id:
        return render(request, 'claim/already_claimed.html', {'place': place})

    if request.method == 'POST':
        form = ClaimRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            token = make_claim_token(place.id, email)
            verify_path = reverse('claim:verify', args=[token])
            verify_url = request.build_absolute_uri(verify_path)
            sent = send_claim_invitation(
                to_email=email,
                place_name=place.name,
                verify_url=verify_url,
            )
            return render(request, 'claim/sent.html', {
                'place': place,
                'email': email,
                'sent': sent,
                'verify_url': verify_url if settings.DEBUG else None,
            })
    else:
        form = ClaimRequestForm()

    return render(request, 'claim/start.html', {'place': place, 'form': form})


def verify_claim(request, token):
    try:
        place_id, email = read_claim_token(token)
    except ValueError as e:
        return render(request, 'claim/verify_failed.html', {'reason': str(e)})

    place = get_object_or_404(Place, pk=place_id)

    if place.owner_id and place.owner.email.lower() != email.lower():
        return render(request, 'claim/verify_failed.html', {
            'reason': 'already_claimed',
            'place': place,
        })

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        username = email[:150]
        user = User.objects.create(username=username, email=email)
        user.set_unusable_password()
        user.save()

    if not place.owner_id:
        place.owner = user
        place.source = Place.Source.CLAIMED
        place.save(update_fields=['owner', 'source', 'updated_at'])

    login(request, user, backend=AUTH_BACKEND)
    return redirect('claim:dashboard', place_id=place.id)


def _require_owner(request, place_id):
    if not request.user.is_authenticated:
        return None, render(request, 'claim/login_required.html', {
            'place_id': place_id,
        })
    place = get_object_or_404(Place, pk=place_id)
    if place.owner_id != request.user.id:
        return None, HttpResponseForbidden('No sos el dueño de este negocio.')
    return place, None


def dashboard(request, place_id):
    place, err = _require_owner(request, place_id)
    if err is not None:
        return err
    services = place.services.all()
    return render(request, 'claim/dashboard.html', {
        'place': place,
        'services': services,
    })


def service_create(request, place_id):
    place, err = _require_owner(request, place_id)
    if err is not None:
        return err

    if request.method == 'POST':
        form = ServiceOfferingForm(request.POST)
        if form.is_valid():
            svc = form.save(commit=False)
            svc.place = place
            svc.save()
            return redirect('claim:dashboard', place_id=place.id)
    else:
        form = ServiceOfferingForm()

    return render(request, 'claim/service_form.html', {
        'place': place, 'form': form, 'mode': 'create',
    })


def service_edit(request, place_id, pk):
    place, err = _require_owner(request, place_id)
    if err is not None:
        return err

    service = get_object_or_404(ServiceOffering, pk=pk, place=place)

    if request.method == 'POST':
        form = ServiceOfferingForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            return redirect('claim:dashboard', place_id=place.id)
    else:
        form = ServiceOfferingForm(instance=service)

    return render(request, 'claim/service_form.html', {
        'place': place, 'form': form, 'mode': 'edit', 'service': service,
    })


def service_delete(request, place_id, pk):
    place, err = _require_owner(request, place_id)
    if err is not None:
        return err

    service = get_object_or_404(ServiceOffering, pk=pk, place=place)

    if request.method == 'POST':
        service.delete()
        return redirect('claim:dashboard', place_id=place.id)

    return render(request, 'claim/service_confirm_delete.html', {
        'place': place, 'service': service,
    })
