# BOS GEMN

A Flask-based betting oversight system.

## Local setup

1. Activate the project virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Run the app:
   ```powershell
   python app.py
   ```
4. Open in browser:
   ```text
   http://127.0.0.1:5000
   ```

## Deployment

This project is ready for deployment with Render or Heroku:

- `requirements.txt`
- `runtime.txt`
- `Procfile`
- `render.yaml`

### Render

1. Create a Render account.
2. Connect your GitHub repository.
3. Add a Web Service with `python` env.
4. Use `pip install -r requirements.txt` as the build command.
5. Use `gunicorn app:app` as the start command.
6. Set environment variables as needed.

### Heroku

1. Install Git and the Heroku CLI.
2. Initialize git:
   ```powershell
   git init
   git add .
   git commit -m "Initial commit"
   ```
3. Deploy:
   ```powershell
   heroku create
   git push heroku main
   ```

## Notes

- The app currently uses SQLite by default in `config.py`.
- For production, use a managed database and set `DATABASE_URL`.
