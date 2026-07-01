# Contributing

This project was created as a technical assessment prototype.

Suggested contribution workflow:

1. Create a branch.
2. Run the app locally or through Docker.
3. Run tests:

```bash
python -m unittest discover -s tests
```

4. Keep secrets out of source control.
5. Avoid committing commercial alcohol label artwork or other third-party copyrighted assets.

## Code style

- Keep extraction logic in `ai/`.
- Keep validation logic in `validator/`.
- Keep demo data separate from application logic.
- Prefer reviewer-friendly error messages.
