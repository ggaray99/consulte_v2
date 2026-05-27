"""
Transactional email for claim flow.

No-op-if-unconfigured: if RESEND_API_KEY is missing, log the link to stdout
so the dev can copy-paste from console. In DEBUG, also return the link in
the response context so the UI can show it.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def send_claim_invitation(*, to_email, place_name, verify_url):
    """Try to send an invitation email. Returns True on success, False otherwise.

    Never raises — caller can show a friendly message regardless of outcome.
    """
    if not settings.RESEND_API_KEY:
        logger.info(
            'RESEND_API_KEY not set. Claim link for %s (%s): %s',
            place_name, to_email, verify_url,
        )
        return False

    try:
        import resend
    except ImportError:
        logger.warning('resend SDK not installed; cannot send claim email.')
        return False

    resend.api_key = settings.RESEND_API_KEY
    try:
        resend.Emails.send({
            'from': settings.DEFAULT_FROM_EMAIL,
            'to': to_email,
            'subject': f'Reclamá {place_name} en consulte.',
            'html': _claim_email_html(place_name, verify_url),
        })
        return True
    except Exception as e:
        logger.warning('Resend send failed for %s: %s', to_email, e)
        return False


def _claim_email_html(place_name, verify_url):
    return f"""<!doctype html>
<html lang="es-ar">
<body style="margin:0;padding:0;background:#F8F9FF;font-family:'Manrope',system-ui,sans-serif;color:#0B1C30;">
  <div style="max-width:560px;margin:0 auto;padding:40px 24px;">
    <div style="background:#0047AB;color:#fff;padding:20px 28px;border-radius:12px 12px 0 0;">
      <span style="font-weight:600;font-size:22px;letter-spacing:-0.045em;">consulte<span style="color:#fff;">.</span></span>
    </div>
    <div style="background:#fff;padding:32px 28px;border:1px solid #E5E9F0;border-top:0;border-radius:0 0 12px 12px;">
      <div style="font-family:monospace;font-size:11px;color:#0047AB;text-transform:uppercase;letter-spacing:0.14em;margin-bottom:10px;">Reclamo de negocio</div>
      <h1 style="font-size:24px;font-weight:600;letter-spacing:-0.015em;margin:0 0 16px;">Tomá control de {place_name}</h1>
      <p style="font-size:15px;line-height:1.55;color:#4A5A6E;margin:0 0 24px;">
        Para confirmar que sos el dueño, hacé clic en el botón. El link es válido por 24 horas.
      </p>
      <a href="{verify_url}" style="display:inline-block;background:#0047AB;color:#fff;text-decoration:none;font-weight:600;font-size:15px;padding:14px 28px;border-radius:8px;">
        Confirmar reclamo
      </a>
      <p style="font-size:13px;color:#6F7E92;margin:32px 0 0;">
        Si no fuiste vos, ignorá este mail.
      </p>
    </div>
    <p style="font-family:monospace;font-size:11px;color:#A2AEBE;text-align:center;letter-spacing:0.08em;margin-top:24px;">
      powered by consulte.
    </p>
  </div>
</body>
</html>"""
