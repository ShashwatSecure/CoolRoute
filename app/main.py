"""CoolRoute operational dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.chat import show_chat
from app.formatters import map_coordinates
from db.queries import (
	get_active_shipments,
	get_latest_active_telemetry,
	get_temperature_history,
)


st.set_page_config(page_title="CoolRoute", page_icon="🚚", layout="wide")


@st.cache_data(ttl=60)
def load_shipments() -> pd.DataFrame:
	return pd.DataFrame(get_active_shipments())


@st.cache_data(ttl=60)
def load_latest_telemetry() -> pd.DataFrame:
	return pd.DataFrame(get_latest_active_telemetry())


@st.cache_data(ttl=60)
def load_temperature_history(vehicle_id: int, hours: int = 24) -> pd.DataFrame:
	return pd.DataFrame(get_temperature_history(vehicle_id, hours))


def show_dashboard() -> None:
	st.title("CoolRoute Dispatch Console")
	st.caption("Cold-chain operations at a glance")
	shipments = load_shipments()
	telemetry = load_latest_telemetry()
	if shipments.empty or telemetry.empty:
		st.warning("No active shipment telemetry is available. Run `python scripts/seed.py` first.")
		return

	active_trucks = int(telemetry["vehicle_id"].nunique())
	in_range = telemetry["cargo_temp_c"].between(telemetry["min_temp_c"], telemetry["max_temp_c"])
	alerts = (~in_range | telemetry["door_open"].astype(bool)).sum()
	kpi_columns = st.columns(3)
	kpi_columns[0].metric("Active trucks", active_trucks)
	kpi_columns[1].metric("Temperature in range", f"{in_range.mean() * 100:.1f}%")
	kpi_columns[2].metric("Alerts", int(alerts), delta="Needs review" if alerts else "All clear", delta_color="inverse")

	st.subheader("Active shipments")
	st.dataframe(
		shipments[["shipment_id", "vehicle_id", "cargo_type", "origin", "destination", "eta", "status"]],
		use_container_width=True,
		hide_index=True,
	)

	left, right = st.columns(2)
	with left:
		st.subheader("Latest truck positions")
		st.map(map_coordinates(telemetry))
	with right:
		st.subheader("Cargo temperature")
		selected_vehicle = st.selectbox("Vehicle", telemetry["vehicle_id"].tolist(), format_func=lambda value: f"Truck {value}")
		if selected_vehicle is None:
			st.info("Select a vehicle to view its temperature history.")
			return
		vehicle_id = int(selected_vehicle)
		history = load_temperature_history(vehicle_id)
		if history.empty:
			st.info("No temperature history is available for this vehicle.")
		else:
			chart = history.set_index("ts")[["cargo_temp_c", "min_temp_c", "max_temp_c"]]
			st.line_chart(chart, y=["cargo_temp_c", "min_temp_c", "max_temp_c"])


def show_placeholder(title: str, message: str) -> None:
	st.title(title)
	st.info(message)


st.sidebar.title("CoolRoute")
page = st.sidebar.radio("Navigate", ["Dashboard", "Chat", "Audit"])
if page == "Dashboard":
	show_dashboard()
elif page == "Chat":
	show_chat()
else:
	show_placeholder("Audit", "Audit events will be added in Phase 6.")

