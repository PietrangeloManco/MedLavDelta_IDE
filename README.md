# MedLavDelta_IDE

I built MedLavDelta as the management platform used by CentroDeltaSrl to simplify occupational-medicine workflows. The platform is deployed at [medlavdelta.it](https://medlavdelta.it/) and is meant to support the daily operational work around Medicina del Lavoro.

## Live Project

- Website: [https://medlavdelta.it/](https://medlavdelta.it/)

## What I Built

The platform is designed so that health companies working with Centro Delta can register themselves and their workers, while Centro Delta manages the administrative side of the system.

The main workflows covered by the application include:

- company onboarding and management,
- worker registration and organization,
- occupational-health records,
- medical visit outcomes and expirations,
- company and medical document management,
- notifications and dashboard flows for the different user roles.

## Tech Stack

I built the platform with:

- Django
- PostgreSQL
- Pillow
- ReportLab
- svglib

## Main Django Apps

- `apps.accounts`
- `apps.aziende`
- `apps.commerciale`
- `apps.sanitaria`
- `apps.notifiche`

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

On Windows, activate the environment with `.venv\\Scripts\\activate`.

## Configuration

The project expects runtime values for:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- email-related settings used by the platform

## Notes

- The platform is role-based and mirrors the actual operational structure of the business.
- Uploaded company and health documents are part of the normal workflow, so any production deployment should be configured with persistent media storage.
