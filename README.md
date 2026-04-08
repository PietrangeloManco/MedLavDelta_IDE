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

## Product Workflow

MedLavDelta is not a generic demo dashboard: I built it as an operational platform around the actual workflow of occupational medicine.

The publishable product flow includes:

- a Centro Delta administrative dashboard for global activity overview,
- company-specific workspaces where each client can manage workers and supporting documents,
- expiry-oriented views that help track visits and medical-document deadlines,
- role-aware navigation that separates internal administration from company-side usage.

I am also preparing redacted screenshots for the README. Any personal data visible in production-like screens, such as names, surnames, emails, or phone numbers, will be censored before publication.

## Screenshots

### Administrative overview

![MedLavDelta admin dashboard](assets/screenshots/admin-dashboard-redacted.png)

### Company workspace

![MedLavDelta company workspace](assets/screenshots/company-workspace-redacted.png)

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
- Because this is a company platform, the public repository documents the product structure and workflow, but not business-sensitive runtime data.
