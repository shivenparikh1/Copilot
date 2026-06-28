# Global Sourcing Copilot

Structured sourcing decision workspace for product requirement intake, supplier discovery, landed cost analysis, lead-time comparison, supplier scoring, risk review, and final recommendation memos.

The repository includes two frontends:

- React/Vite portfolio app in `src/`
- Streamlit Cloud-ready app in `streamlit_app.py`

There are two Streamlit-related Python files:

- `streamlit_app.py` is the active deployed app file. It contains `st.set_page_config`, the main app layout, and the Supplier Scorecard.
- `app.py` is a small launcher that imports `main` from `streamlit_app.py`; it exists for tools that expect an `app.py` filename.

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

The Streamlit app starts with a brief overview screen. Click **Continue** to open the sourcing workflow. It does not preload product or supplier data. Use **Load demo** inside the app only when you want sample data for testing.

New sourcing workflow sections include:

- **Weights** for changing top-level scoring weights, individual field weights, and the transparent Supplier Scorecard model.
- **News** for current sourcing, trade, logistics, and supplier-risk headlines from a public RSS feed cached for one week.
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
- Does not connect to a backend integration.
- Requirement review, sample suppliers, sourcing notes, and memo generation use rule-based placeholder logic.
- Supplier data confidence labels include Verified, Supplier Quote, Public Estimate, AI Estimate, Manual Review Needed, and Unavailable Online.
