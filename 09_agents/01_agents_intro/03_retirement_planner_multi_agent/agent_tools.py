import pandas as pd
import yfinance as yf
import pandas_datareader as pdr
from arch import arch_model
import statsmodels.api as sm
import numpy as np
from functools import reduce
from typing import List
from smolagents import tool
import datetime as dt


@tool
def get_today() -> str:
    """Returns today's date in YYYY-MM-DD format.

    Examples:
        >>> get_today()
        '2025-01-27'  # Example output, will vary depending on the current date

    Returns:
        str: Today's date as a string.
    """
    return dt.datetime.now().strftime("%Y-%m-%d")


@tool
def get_ticker_data(
    tickers: List[str],
    start_date: str,
    end_date: str,
    metric: str = "all",
    sampling: str = "monthly",
) -> dict:
    """Downloads historical stock data from Yahoo Finance and returns it as a dictionary.

    Examples:
        >>> get_ticker_data(["AAPL"], "2023-01-01", "2023-12-31", "Close", "weekly")
        {"AAPL": [{"Date": "2023-01-06", "Close": 129.619995}, {"Date": "2023-01-13", "Close": 134.759995}, ...]}

        >>> get_ticker_data(["AAPL", "MSFT"], "2023-01-01", "2023-12-31", "all", "monthly")
        {"AAPL": [{"Date": "2023-01-31", "Open": 144.479996, "High": 147.229996, "Low": 141.320007, "Close": 144.289993, "Adj Close": 143.839996, "Volume": 77663600}, ...],
          "MSFT": [{"Date": "2023-01-31", "Open": 250.089996, "High": 256.25, "Low": 242.529999, "Close": 252.509995, "Adj Close": 251.873795, "Volume": 47146900}, ...]}

    Args:
        tickers: A list of stock ticker symbols (e.g., ["AAPL", "MSFT"]).
        start_date: The start date for the data (e.g., "2023-01-01").
        end_date: The end date for the data in YYYY-MM-DD format (e.g., "2023-12-31").
        metric:  If "all", returns all available data columns (Open, High, Low, Close, Volume).
            Otherwise, specifies a single metric to return (e.g., "Close"). Defaults to "all".
        sampling: The frequency of the data. Can be "daily", "weekly", or "monthly". Defaults to "monthly".

    Returns:
        dict: A dictionary where keys are ticker symbols and values are lists of historical data records.
             Each record is a dictionary containing 'Date' and the requested metrics.

    Raises:
        ValueError: If an invalid sampling frequency is provided.


    """

    df = yf.download(tickers, start=start_date, end=end_date)

    if metric != "all":
        df = df[metric]

    if sampling == "weekly":
        df = df.resample("WE").last()
    elif sampling == "monthly":
        df = df.resample("ME").last()
    elif sampling == "quarterly":
        df = df.resample("QE").last()
    elif sampling == "daily":
        pass
    else:
        raise ValueError(
            "Invalid sampling frequency. Use 'daily', 'weekly', 'monthly', 'quarterly."
        )

    result = {}
    for ticker in tickers:
        if metric == "all":
            df_tick = df.loc[:, (slice(None), ticker)]
            df_tick.columns = df_tick.columns.droplevel("Ticker")
        else:
            df_tick = df.loc[:, ticker]
            df_tick = df_tick.to_frame(name=metric)
        df_tick = df_tick.reset_index()
        df_tick["Date"] = df_tick["Date"].dt.strftime("%Y-%m-%d")
        result[ticker] = df_tick.to_dict(orient="records")

    return result


@tool
def get_fred_data(
    series: str, start_date: str, end_date: str, sampling: str = "monthly"
) -> list[dict]:
    """Downloads data from the Federal Reserve Economic Data (FRED) database and returns it as dictionary.

    Examples:
        >>> get_fred_data("GDP", "2023-01-01", "2023-01-10")
        [{"Date": "2023-01-01", "GDP": 21.0}, {"Date": "2023-01-02", "GDP": 22.0}, ...]

    Args:
        series: The FRED series ID (e.g., "GDP").
        start_date: The start date for the data (e.g., "2023-01-01").
        end_date: The end date for the data in YYYY-MM-DD format (e.g., "2023-12-31").
        sampling: The frequency of the data. Can be "monthly", "quarterly", or "yearly". Defaults to "monthly".

    Returns:
        list: A list representing a list of dictionaries, where each dictionary contains 'Date' and the value of the FRED series.

    Raises:
        ValueError: If an invalid sampling frequency is provided.


    """
    df = pdr.data.DataReader(series, start=start_date, end=end_date, data_source="fred")

    if sampling == "monthly":
        df = df.resample("ME").last()
    elif sampling == "quarterly":
        df = df.resample("QE").last()
    elif sampling == "yearly":
        df = df.resample("YE").last()
    else:
        raise ValueError(
            "Invalid sampling frequency. Use 'monthly', 'quarterly', or 'yearly'."
        )

    df.reset_index(inplace=True)
    df["DATE"] = df["DATE"].dt.strftime("%Y-%m-%d")
    df.rename(columns={"DATE": "Date"}, inplace=True)

    result = df.to_dict(orient="records")

    return result


@tool
def run_ols_regression(y: List[float], X: List[float]) -> dict:
    """Runs a simple Ordinary Least Squares (OLS) regression.
    I using to compute beta, make sure the dates are aligned.

    Examples:
        >>> y = [1, 2, 3, 4, 5]
        >>> X = [2, 4, 5, 4, 5]
        >>> run_ols_regression(y, X)
        {"const": -0.4, "coef": 0.9}

    Args:
        y: The dependent variable.
        X: The independent variable(s).

    Returns:
        dict: A dictionary containing the constant and coefficient of the OLS regression.


    """
    X = np.array(X)
    y = np.array(y)
    X = sm.add_constant(X)
    model = sm.OLS(y, X)
    results = model.fit()
    params = results.params
    const, coef = params
    return {"const": const, "coef": coef}


@tool
def simulate_investment_roi(
    tickers: List[str],
    horizon: int,
    initial_investment: float,
    monthly_contribution: float = 0,
    num_simulations: int = 1000,
) -> dict:
    """Simulates the return on investment (ROI) for a given stock over a specified time period.
        Monthly contribution should be 0 unless otherwise specified.

    Examples:
        >>> simulate_investment_roi(tickers=["AAPL"], horizon=120, initial_investment=10000, monthly_contribution=100, num_simulations=1000)
        {'average_roi': 0.15, 'expected_account_value': 50000}

        >>> simulate_investment_roi(tickers=["AAPL", "MSFT"], horizon=120, initial_investment=10000, monthly_contribution=100, num_simulations=1000)
        {'average_roi': 0.10, 'expected_account_value': 15000}

    Args:
        tickers: The stock ticker symbols (e.g., ["AAPL"]).
        horizon: The investment horizon in months.
        initial_investment: The initial investment amount.
        monthly_contribution: The monthly contribution amount. Defaults to 0.
        num_simulations: The number of simulations to run. Defaults to 1000.

    Returns:
        dict: A dictionary containing the average ROI and the ending account value.


    """

    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    historic_data = get_ticker_data(tickers, "1945-01-01", today, metric="Close")
    historic_data = reduce(
        lambda x, y: x.merge(
            y, on="Date", suffixes=[len(x.columns), len(x.columns) + 1]
        ),
        [pd.DataFrame(historic_data[ticker]) for ticker in tickers],
    ).dropna()
    historic_data["Date"] = pd.to_datetime(historic_data["Date"])
    historic_data.set_index("Date", inplace=True)
    historic_data = historic_data.sum(axis=1)

    monthly_historic_data = historic_data.resample("ME").last()
    monthly_returns = monthly_historic_data.pct_change().dropna()

    rois = []
    for n in range(num_simulations):
        # returns = np.random.choice(monthly_returns.values, horizon)
        total_investment = initial_investment
        for i in range(horizon):
            total_investment += monthly_contribution
            total_investment *= 1 + np.random.choice(monthly_returns.values)
        roi = (total_investment - initial_investment) / initial_investment
        rois.append(roi)

    percent_roi = np.mean(rois)
    expected_account_value = (
        initial_investment * (1 + percent_roi) + monthly_contribution * horizon
    )

    return {
        "average_roi": percent_roi,
        "expected_account_value": expected_account_value,
    }


@tool
def forecast_volatility(ticker: str, start_date: str, end_date: str) -> float:
    """Forecasts volatility using an ARCH model.

    Examples:
        >>> forecast_volatility("AAPL", "2023-01-01", "2023-01-10")
        0.2

    Args:
        ticker: The stock ticker symbol (e.g., "AAPL").
        start_date: The start date for the data (e.g., "2023-01-01").
        end_date: The end date for the data in YYYY-MM-DD format (e.g., "2023-12-31").

    Returns:
        float: The forecasted volatility


    """
    prices = get_ticker_data([ticker], start_date, end_date, metric="Close")

    prices = pd.DataFrame(prices[ticker])
    prices["Date"] = pd.to_datetime(prices["Date"])
    prices.set_index("Date", inplace=True)

    returns = 100 * prices.pct_change().dropna()

    horizon = 63
    am = arch_model(returns)
    res = am.fit()
    forecasts = res.forecast(horizon=horizon)
    forecast_volatility = (
        forecasts.residual_variance.iloc[-1, :].sum() * 252 / horizon
    ) ** 0.5 / 100
    return forecast_volatility


@tool
def simulate_retirement(
    initial_account_value: float,
    num_years: int,
    annual_spend: float,
    mean_returns: float = 0.01,
    std_returns: float = 0,
    inflation: float = 0.03,
    num_sims: int = 1000,
) -> dict:
    """Simulates whether a retirement account will last for a specified number of years.

    Examples:
        >>> simulate_retirement(1000000, 30, 40000, 0.07, 0.15, 0.03)
        {'likelihood_of_running_out': 0.2, 'average_years_last': 25}

    Args:
        initial_account_value: The initial retirement account value.
        num_years: The number of years to simulate.
        annual_spend: The annual spending amount.
        mean_returns: The mean annual return . Defaults to 0.01.
        std_returns: The standard deviation of annual returns. Defaults to 0.
        inflation: The annual inflation rate. Defaults to 0.03.
        num_sims: The number of simulations to run. Defaults to 1000.

    Returns:
        dict: A dictionary containing the likelihood of running out of money and the average number of years the account will last.


    """
    account_value = initial_account_value

    if std_returns == 0:
        returns = np.full((num_sims, num_years + 1), mean_returns)
    else:
        returns = np.random.normal(mean_returns, std_returns, (num_sims, num_years + 1))

    wealth = np.empty((num_sims, num_years + 1))
    wealth[:, :] = np.nan
    wealth[:, 0] = account_value

    count_bankrupt = 0
    years_lasted = []

    for sim in range(num_sims):
        spend = annual_spend
        for year in range(1, num_years + 1):
            next_period_wealth = (wealth[sim, year - 1] - spend) * (
                1 + returns[sim, year]
            )
            if next_period_wealth < 0:
                count_bankrupt += 1
                years_lasted.append(year)
                break
            else:
                wealth[sim, year] = next_period_wealth
                spend *= 1 + inflation
        years_lasted.append(num_years)

    likelihood_of_running_out = count_bankrupt / num_sims
    average_years_last = np.mean(years_lasted)
    return {
        "likelihood_of_running_out": likelihood_of_running_out,
        "average_years_last": average_years_last,
    }
