# Nigeria's Income-Health Gap - Streamlit dashboard

Interactive dashboard over the World Bank panel (Nigeria + six African peers, 2000-2023).

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

It opens at http://localhost:8501.

## Data

By default the app pulls live from the World Bank with `wbgapi` and caches it.
If `nigeria_peers_wide.csv` (the file your notebook saves) sits next to `app.py`,
the app loads that instead, so it also runs offline.

## Requirements met

- UI interaction: sidebar outcome selectbox, year slider, country multiselect, log-scale toggle.
- Within-visualization interaction: drag a brush on the scatter; click a bar.
- Tooltips: hover any point, bar, or line.
- Two coordinated visualizations: brushing the scatter filters the ranked bar;
  clicking a bar highlights that country in the scatter and the time-series chart.
