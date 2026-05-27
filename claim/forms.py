from django import forms

from .models import ServiceOffering


class ClaimRequestForm(forms.Form):
    email = forms.EmailField(
        label='Tu email',
        widget=forms.EmailInput(attrs={
            'placeholder': 'tu@email.com',
            'autocomplete': 'email',
            'autofocus': 'autofocus',
        }),
    )


class ServiceOfferingForm(forms.ModelForm):
    class Meta:
        model = ServiceOffering
        fields = ['name', 'description', 'price', 'duration_minutes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Consulta de rutina'}),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Detalles del servicio (opcional)',
            }),
            'price': forms.NumberInput(attrs={
                'step': '0.01',
                'placeholder': '15000',
            }),
            'duration_minutes': forms.NumberInput(attrs={'min': '5', 'step': '5'}),
        }
