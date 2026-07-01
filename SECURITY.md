# Security

## Secrets

Do not commit API keys, tokens, passwords, or private configuration files to this repository.

The application supports OpenAI Vision as an optional enhancement. API keys may be supplied through:

- the `OPENAI_API_KEY` environment variable, or
- the Streamlit sidebar for the current session.

The application does not intentionally write API keys to disk.

## Data handling

This prototype is designed for local evaluation. Uploaded label images and reviewer notes are processed in memory during the Streamlit session and are not persisted by default.

## Public repository caution

The repository intentionally includes synthetic labels only. Do not commit commercial brand artwork or downloaded COLA label images unless you have the right to redistribute them.

## Reporting issues

For this assessment project, report issues directly through the repository owner or reviewer contact channel.
