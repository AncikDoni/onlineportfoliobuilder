# Forma — Online Portfolio Builder

A lightweight Flask portfolio builder for creating and sharing a personal professional portfolio. Edit your profile, skills, contact details, color theme, and project list. Changes are stored locally in SQLite and rendered as a public portfolio page.

## Features

- Responsive landing page and portfolio preview.
- Profile editor for your name, professional title, bio, email, location, website, skills, public slug, and theme.
- Add and remove projects, including optional year, category, and external link.
- Public portfolio at `/p/<your-slug>` with contact links.
- Copyable public portfolio URL in the home preview and profile editor.
- SQLite persistence with starter content on first run.
- Basic input validation and automated route tests.

This starter is a single-user portfolio demo, not a multi-user service. The public portfolio is read-only; the editor and project changes require the `ADMIN_PASSWORD` configured on the host. Do not reuse a personal account password. This lightweight protection is not a substitute for a security review before handling sensitive information.

## Run on Windows

1. Open PowerShell in this project directory.
2. Create and activate a virtual environment:
   - `py -m venv .venv`
   - `.venv\Scripts\Activate.ps1`
3. Install dependencies: `py -m pip install -r requirements.txt`
4. Start the app: `py app.py`
5. Open `http://127.0.0.1:5000` in a browser.

The app creates `portfolio.db` automatically and inserts demo profile/project content the first time it starts. Edit your content using **Customize portfolio**. The configured public page is available at `/p/alex-morgan` unless you change the slug.

Use **Copy link** on the home page or in the editor to copy the full portfolio URL. Locally, the address is only reachable from your own computer by default. After deployment, the copied URL uses the public host address.

## Deploy to Render

The included `render.yaml` configures a Render web service using Gunicorn and a persistent disk for the SQLite database. A persistent disk requires a paid Render web-service plan; without it, portfolio edits can be lost when the service restarts or redeploys.

1. Push this project to a GitHub repository you control. Do not commit secrets or your local `portfolio.db`.
2. Sign in to Render, create a **Blueprint**, and connect that repository. Render reads `render.yaml` and shows the service and disk configuration before creation.
3. When prompted for `ADMIN_PASSWORD`, set a strong, unique password. Keep it private; the browser will prompt for credentials when you open **Customize portfolio**. The username can be any value.
4. Review the paid plan and persistent-disk cost shown by Render, then create the service.
5. After deployment succeeds, open the generated `onrender.com` address. Update the profile and use **Copy link** to share the public portfolio URL.

The public profile is accessible to anyone with the link. Editing routes are protected by the configured password. Treat Render's generated URL as the shareable address; the local `localhost` address will not work for others. Render manages the generated `SECRET_KEY` and the app writes SQLite data under `/var/data` on the persistent disk.

## Run tests

With the virtual environment activated, run `py -m unittest discover -s tests -v`.

## Configuration

- `PORTFOLIO_DATABASE`: optional SQLite database file path.
- `SECRET_KEY`: session signing key; Render generates one through `render.yaml`.
- `ADMIN_PASSWORD`: required to access edit and project-management routes on Render. The hosted editor fails closed if it is missing.
- `FLASK_DEBUG=1`: enables Flask debug mode for local development only.

The interface uses system font stacks and works without external font services.
