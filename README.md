# Global Sourcing Copilot

AI-assisted sourcing decision workspace for product requirement intake, supplier discovery, landed cost analysis, lead-time comparison, supplier scoring, risk review, and final recommendation memos.

The repository includes two frontends:

- React/Vite portfolio app in `src/`
- Streamlit Cloud-ready app in `streamlit_app.py`

## Streamlit Deployment

Use this as the Streamlit main file path:

```text
streamlit_app.py
```

Streamlit Cloud should install Python dependencies from:

```text
requirements.txt
```

Local run:

```bash
python -m streamlit run streamlit_app.py
```

The Streamlit app starts as a blank guided workflow. It does not preload product or supplier data. Use **Load demo** inside the app only when you want sample data for testing.

New sourcing workflow sections include:

- **Framework Weights** for changing both top-level scoring weights and individual field weights.
- **Weekly News** for current sourcing, trade, logistics, and supplier-risk headlines from a public RSS feed cached for one week.
- **Sourcing Excel Upload** for extracting matching product requirements and supplier rows from `.xlsx` workbooks.

## React App

Local run:

```bash
pnpm install
pnpm dev
```

Production build:

```bash
pnpm build
```

## MVP Notes

- Includes optional sample sourcing data for demos.
- Includes configurable category and field-level scoring weights.
- Includes public RSS-based weekly news updates for current sourcing context.
- Can prefill matching requirement and supplier fields from uploaded sourcing Excel workbooks while leaving unmatched fields blank.
- Stores edits in local browser/session state depending on frontend.
- Does not connect to a backend or live AI API.
- AI review, supplier suggestions, insights, and memo generation use rule-based placeholder logic.
- Supplier data confidence labels include Verified, Estimated, AI Suggested, Needs Manual Review, and Unavailable Online.
