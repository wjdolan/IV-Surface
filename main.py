# Implied volatility surface Streamlit app

import datetime as dt

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import seaborn as sns
import yfinance as yf
import plotly.graph_objects as go

sns.set_theme(style="whitegrid")


def get_current_price(ticker_obj: yf.Ticker) -> float:
  """Return the latest available price with fallbacks for stability."""
  price = None

  fast = getattr(ticker_obj, "fast_info", None)
  if fast:
    price = fast.get("lastPrice") or fast.get("last_price")

  if price is None:
    info = ticker_obj.info or {}
    price = info.get("currentPrice") or info.get("regularMarketPrice")

  if price is None:
    hist = ticker_obj.history(period="1d")
    if not hist.empty and "Close" in hist.columns:
      price = hist["Close"].iloc[-1]

  if price is None:
    raise ValueError(f"Could not determine a current price for {ticker_obj.ticker}")

  return float(price)


def get_option_data(ticker: str, option_type: str = "calls") -> pd.DataFrame:
  ticker_obj = yf.Ticker(ticker)
  try:
    expirations = ticker_obj.options
  except Exception as exc:
    raise RuntimeError(f"Failed to fetch option expirations for {ticker}: {exc}") from exc

  if not expirations:
    raise ValueError(f"No option expirations available for {ticker}")

  df = pd.DataFrame()
  errors = []

  for exp in expirations:
    try:
      chain = ticker_obj.option_chain(exp)
      new_option = chain.puts if option_type == "puts" else chain.calls
    except Exception as exc:
      errors.append((exp, exc))
      continue

    new_option["expiration"] = pd.to_datetime(exp)
    df = pd.concat([df, new_option], ignore_index=True)

  if df.empty:
    if errors:
      first_exp, first_err = errors[0]
      raise RuntimeError(f"Failed to load option chains; first error at {first_exp}: {first_err}") from first_err
    raise ValueError(f"No option data returned for {ticker}")

  df.drop(
      [
          "lastTradeDate",
          "lastPrice",
          "bid",
          "ask",
          "change",
          "percentChange",
          "openInterest",
          "inTheMoney",
          "contractSize",
          "currency",
          "volume",
      ],
      axis=1,
      inplace=True,
      errors="ignore",
  )

  df["daysToExpiration"] = (df.expiration - dt.datetime.today()).dt.days + 1

  return df


def term_structure_graph(options_data: pd.DataFrame, ticker: str, option_type: str = "calls"):
  ticker_obj = yf.Ticker(ticker)
  price = get_current_price(ticker_obj)

  strikes = options_data["strike"].dropna()

  if option_type == "puts":
    strikes = strikes[strikes > price]
    if strikes.empty:
      raise ValueError(f"No strikes above price {price} for {ticker}")
    atm_strike = strikes.min()
  else:
    strikes = strikes[strikes < price]
    if strikes.empty:
      raise ValueError(f"No strikes below price {price} for {ticker}")
    atm_strike = strikes.max()

  atm_options_data = options_data[options_data["strike"] == atm_strike].copy()
  atm_options_data.set_index("expiration", inplace=True)

  fig, ax = plt.subplots(figsize=(12, 8))
  base_fs = plt.rcParams.get("font.size", 10) + 2
  plot_data = atm_options_data.reset_index()
  sns.lineplot(
      data=plot_data,
      x="expiration",
      y="impliedVolatility",
      marker="o",
      color="tab:blue",
      ax=ax,
  )

  ax.set_xlabel("Expiration", fontsize=base_fs)
  ax.set_ylabel("Implied Volatility", fontsize=base_fs)
  ax.set_title("Implied Volatility Term Structure", fontsize=base_fs + 1)
  ax.tick_params(labelsize=base_fs)
  ax.grid(True, linestyle="--", alpha=0.7)
  ax.legend(["Implied Volatility"], loc="upper right", fontsize=base_fs)

  return fig


def volatility_curve_graph(options_data: pd.DataFrame, price: float):
  """Plot strike vs implied vol for the nearest expiration (ATM smile)."""
  if options_data.empty:
    raise ValueError("No option data to plot volatility curve.")

  nearest_exp = options_data["expiration"].min()
  exp_slice = options_data[options_data["expiration"] == nearest_exp].copy()
  if exp_slice.empty:
    raise ValueError("No options found for the nearest expiration.")

  exp_slice.sort_values("strike", inplace=True)
  atm_idx = (exp_slice["strike"] - price).abs().idxmin()
  atm_strike = exp_slice.loc[atm_idx, "strike"]

  fig, ax = plt.subplots(figsize=(12, 8))
  base_fs = plt.rcParams.get("font.size", 10) + 2
  sns.lineplot(
      data=exp_slice,
      x="strike",
      y="impliedVolatility",
      marker="o",
      color="tab:blue",
      ax=ax,
  )

  ax.axvline(atm_strike, color="red", linestyle="--", linewidth=1, label=f"Spot strike ~{atm_strike:.2f}")
  ax.set_title("Volatility Curve", fontsize=base_fs + 1)
  ax.set_xlabel("Strike Price", fontsize=base_fs)
  ax.set_ylabel("Implied Volatility", fontsize=base_fs)
  ax.tick_params(labelsize=base_fs)
  ax.grid(True, linestyle="--", alpha=0.7)
  ax.legend(loc="upper right", fontsize=base_fs)

  return fig


def iv_surface_graph(options_data: pd.DataFrame, price: float | None = None):
  surface = (
      options_data[["daysToExpiration", "strike", "impliedVolatility"]]
      .pivot_table(values="impliedVolatility", index="strike", columns="daysToExpiration")
      .dropna()
  )

  x, y, z = surface.columns.values, surface.index.values, surface.values
  X, Y = np.meshgrid(x, y)

  fig = go.Figure(
      data=[
          go.Surface(
              x=X,
              y=Y,
              z=z,
              colorscale="Spectral",
              opacity=0.9,
              showscale=True,
          )
      ]
  )

  fig.update_layout(
      title="Implied Volatility Surface",
      scene=dict(
          xaxis_title="Days to Expiration",
          yaxis_title="Strike Price",
          zaxis_title="Implied Volatility",
      ),
      width=900,
      height=700,
      margin=dict(l=0, r=0, b=0, t=50),
  )

  if price is not None and not surface.empty:
    # Draw a thin red line at the nearest strike to current price across all expirations.
    nearest_idx = surface.index.get_indexer([price], method="nearest")[0]
    nearest_strike = surface.index[nearest_idx]
    vols_at_strike = surface.iloc[nearest_idx]
    fig.add_trace(
        go.Scatter3d(
            x=surface.columns.values,
            y=np.full_like(surface.columns.values, nearest_strike, dtype=float),
            z=vols_at_strike.values,
            mode="lines",
            line=dict(color="red", width=3),
            name=f"Spot Strike ~{nearest_strike:.2f}",
            showlegend=True,
        )
    )
    fig.add_trace(
        go.Scatter3d(
            x=[float(surface.columns.max())],
            y=[float(nearest_strike)],
            z=[float(np.nanmin(z))],
            mode="text",
            text=[f"Spot {nearest_strike:.2f}"],
            textfont=dict(color="red", size=12),
            showlegend=False,
        )
    )

  return fig


def main():
  st.title("Implied Volatility Surface")
  st.text("(based on Yahoo Finance)")

  ticker = st.text_input("Enter stock ticker", value="XOM").strip().upper()
  info_name = ""
  if ticker:
    try:
      # Try shortName then longName; avoid duplicate fetches later
      t_info = yf.Ticker(ticker).info or {}
      info_name = t_info.get("shortName") or t_info.get("longName") or ""
    except Exception:
      info_name = ""
  if info_name:
    st.write(f"**{info_name}**")

  option_type = st.selectbox("Option type", options=["calls", "puts"], index=0)

  if not ticker:
    st.info("Enter a ticker to load the option chain.")
    return

  try:
    ticker_obj = yf.Ticker(ticker)

    current_price = get_current_price(ticker_obj)
    options_data = get_option_data(ticker, option_type=option_type)
    if options_data.empty:
      st.warning("No option data returned for this ticker.")
      return

    surface_fig = iv_surface_graph(options_data, price=current_price)
    st.plotly_chart(surface_fig, use_container_width=True)

    # Uncomment to display side-by-side term structure and volatility curve plots.
    # col1, col2 = st.columns(2)
    # with col1:
    #   term_fig = term_structure_graph(options_data, ticker, option_type=option_type)
    #   st.pyplot(term_fig)
    #   plt.close(term_fig)
    # with col2:
    #   vol_fig = volatility_curve_graph(options_data, current_price)
    #   st.pyplot(vol_fig)
    #   plt.close(vol_fig)
    
  except Exception as exc:
    st.error(f"Error loading data for {ticker}: {exc}")


if __name__ == "__main__":
  main()
