from django.templatetags.static import static

from apps.aziende.models import Azienda


DEFAULT_PLATFORM_BRANDING = {
    'logo_url': static('Logo_oriz.svg'),
    'logo_alt': 'Centro Delta Logo',
    'is_company_brand': False,
}


def platform_branding(request):
    branding = dict(DEFAULT_PLATFORM_BRANDING)
    user = getattr(request, 'user', None)
    if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_azienda', False):
        return {'platform_branding': branding}

    azienda = getattr(request, 'azienda', None)
    if azienda is None:
        azienda = Azienda.objects.filter(user=user).only('ragione_sociale', 'logo_azienda').first()

    if azienda and azienda.logo_azienda:
        branding.update({
            'logo_url': azienda.logo_azienda.url,
            'logo_alt': f'Logo {azienda.display_name}',
            'is_company_brand': True,
        })

    return {'platform_branding': branding}
