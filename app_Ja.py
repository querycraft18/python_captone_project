from pathlib import Path
import html

import pandas as pd
import plotly.express as px
import streamlit as st

import zipfile
from io import BytesIO
import math

# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Sales Performance & Customer Insights",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

BLUE = "#0247B7"
ORANGE = "#F47A2A"

PALETTE = [
    "#0247B7",
    "#38A3FF",
    "#5B6CFF",
    "#00A6A6",
    "#F47A2A",
    "#8B5CF6",
    "#22C55E",
    "#EAB308",
    "#64748B",
]


# ============================================================
# 2. MODERN DASHBOARD STYLING
# ============================================================

st.markdown(
    f"""
    <style>
        .block-container {{
            padding-top: 1.4rem;
            padding-bottom: 2rem;
        }}

        .hero {{
            border: 1px solid #DCE5F1;
            border-radius: 20px;
            padding: 1.35rem 1.55rem;
            background:
                linear-gradient(
                    135deg,
                    rgba(2,71,183,0.10),
                    rgba(56,163,255,0.03)
                );
            margin-bottom: .9rem;
        }}

        .hero-kicker {{
            color: {BLUE};
            font-size: .78rem;
            font-weight: 800;
            letter-spacing: .09em;
            text-transform: uppercase;
        }}

        .hero-title {{
            color: #172033;
            font-size: 2.15rem;
            font-weight: 800;
            margin-top: .15rem;
            margin-bottom: .2rem;
        }}

        .hero-sub {{
            color: #667085;
            font-size: .98rem;
        }}

        .chips {{
            display: flex;
            flex-wrap: wrap;
            gap: .4rem;
            margin: .25rem 0 1rem 0;
        }}

        .chip {{
            background: #EEF4FF;
            border: 1px solid #D8E6FF;
            color: {BLUE};
            border-radius: 999px;
            padding: .28rem .62rem;
            font-size: .8rem;
            font-weight: 650;
        }}

div[data-testid="stMetric"] {{
    background-color: #EEF4FF;
    padding: 16px;
    border-radius: 14px;
    width: 100%;
    border: 1px solid #9CA3AF;
}}

        /* KPI VALUE - BOLD */
[data-testid="stMetricValue"] {{
    font-weight: 620 !important;
    color: #123E6B !important;
}}

        .section-note {{
            color: #667085;
            font-size: .86rem;
            margin-top: -.4rem;
            margin-bottom: .8rem;
        }}

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. HELPERS
# ============================================================

def compact_number(value, decimals=2):
    if pd.isna(value):
        return "0"

    value = float(value)
    absolute = abs(value)

    if absolute >= 1_000_000_000:
        number = value / 1_000_000_000
        suffix = "B"
    elif absolute >= 1_000_000:
        number = value / 1_000_000
        suffix = "M"
    elif absolute >= 1_000:
        number = value / 1_000
        suffix = "K"
    else:
        return f"{value:,.0f}"

    text = f"{number:.{decimals}f}".rstrip("0").rstrip(".")
    return f"{text}{suffix}"


def clean_money(series):
    return pd.to_numeric(
        series.astype("string")
        .str.replace("₱", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip(),
        errors="coerce",
    )


def find_data_file(candidates):
    roots = [
        Path("data"),
        Path("."),
        Path("/mnt/data"),
    ]

    for root in roots:
        for name in candidates:
            path = root / name
            if path.exists():
                return path

    raise FileNotFoundError(
        "Could not find: " + ", ".join(candidates)
    )


def style_figure(fig, height=410):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(
            l=20,
            r=20,
            t=62,
            b=30,
        ),
        font=dict(
            family="Inter, Arial, sans-serif",
            size=12,
            color="#334155",
        ),
        title=dict(
            font=dict(
                size=17,
                color="#172033",
            ),
            x=.01,
            xanchor="left",
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
        ),
    )
    return fig


def chart_card(fig):
    with st.container(border=True):
        st.plotly_chart(
            fig,
            width="stretch",
        )


def filter_sales(
    dataframe,
    start_date,
    end_date,
    regions,
    channels,
    categories,
    shipping_methods,
):
    result = dataframe[
        dataframe["order_date"].notna()
    ].copy()

    result = result[
        result["order_date"].dt.date.between(
            start_date,
            end_date,
        )
    ]

    if regions:
        result = result[
            result["region_name"].isin(regions)
        ]

    if channels:
        result = result[
            result["sales_channel"].isin(channels)
        ]

    if categories:
        result = result[
            result["category_clean"].isin(categories)
        ]

    if shipping_methods:
        result = result[
            result["shipping_method"].isin(shipping_methods)
        ]

    return result.copy()


def make_filter_chips(
    start_date,
    end_date,
    regions,
    channels,
    categories,
):
    values = [
        f"{start_date:%d %b %Y} – {end_date:%d %b %Y}",
        f"Regions: {len(regions)}",
        f"Channels: {len(channels)}",
        f"Categories: {len(categories)}",
    ]

    tags = "".join(
        (
            '<span class="chip">'
            f"{html.escape(v)}"
            "</span>"
        )
        for v in values
    )

    st.markdown(
        f'<div class="chips">{tags}</div>',
        unsafe_allow_html=True,
    )

# ============================================================
# 4. LOAD + CLEAN ALL SEVEN DATASETS
# ============================================================

@st.cache_data
def load_data():
    customer_file = find_data_file(
        [
            "customers.csv",
            "customers(20261017-082937).csv",
        ]
    )

    product_file = find_data_file(
        [
            "products.csv",
            "products(1).csv",
        ]
    )

    order_file = find_data_file(
        [
            "orders.csv",
            "orders(1).csv",
        ]
    )

    item_file = find_data_file(
        [
            "order_items.csv",
            "order_items(1).csv",
        ]
    )

    payment_file = find_data_file(
        [
            "payments.csv",
            "payments(1).csv",
        ]
    )

    shipment_file = find_data_file(
        [
            "shipments.csv",
            "shipments(1).csv",
        ]
    )

    return_file = find_data_file(
        [
            "returns.csv",
            "returns(1).csv",
        ]
    )

    # --------------------------------------------------------
    # READ RAW FILES
    # --------------------------------------------------------

    customers_raw = pd.read_csv(customer_file)
    products_raw = pd.read_csv(product_file)
    orders_raw = pd.read_csv(order_file)
    items_raw = pd.read_csv(item_file)
    payments_raw = pd.read_csv(payment_file)
    shipments_raw = pd.read_csv(shipment_file)
    returns_raw = pd.read_csv(return_file)

    raw_counts = {
        "Customers": len(customers_raw),
        "Products": len(products_raw),
        "Orders": len(orders_raw),
        "Order Items": len(items_raw),
        "Payments": len(payments_raw),
        "Shipments": len(shipments_raw),
        "Returns": len(returns_raw),
    }

    # --------------------------------------------------------
    # DUPLICATES
    # --------------------------------------------------------

    customers = customers_raw.drop_duplicates().copy()
    products = products_raw.drop_duplicates().copy()
    orders = orders_raw.drop_duplicates().copy()
    items = items_raw.drop_duplicates().copy()
    payments = payments_raw.drop_duplicates().copy()
    shipments = shipments_raw.drop_duplicates().copy()
    returns = returns_raw.drop_duplicates().copy()

    # --------------------------------------------------------
    # CUSTOMERS
    # --------------------------------------------------------

    #Fill missing values
    customers['gender'] = customers['gender'].fillna("Unknown")
    customers['age'] = customers['age'].fillna(0)
    customers['phone'] = customers['phone'].fillna('09100000001')
    customers['email'] = customers['email'].fillna('default@gmail.com')
    customers['loyalty_tier'] = customers['loyalty_tier'].fillna('Unknown')
    
    customers["customer_name"] = (
        customers["first_name"]
        .fillna("")
        .astype(str)
        .str.strip()
        + " "
        + customers["last_name"]
        .fillna("")
        .astype(str)
        .str.strip()
    ).str.strip()

    gender_map = {
          "m": "Male",
          "male": "Male",
          "M": "Male",
          "f": "Female",
          "F": "Female",
          "female": "Female",
          "unknown": "Unknown",
    }

    customers["gender_clean"] = (
        customers["gender"]
        .astype("string")
        .str.strip()
        .str.lower()
        .replace(gender_map)
        .fillna("Unknown")
    )

    customers["age_clean"] = pd.to_numeric(
        customers["age"],
        errors="coerce",
    )

    customers.loc[
        ~customers["age_clean"].between(
            18,
            100,
        ),
        "age_clean",
    ] = pd.NA

    customers["signup_date_clean"] = pd.to_datetime(
        customers["signup_date"],
        format="mixed",
        errors="coerce",
    )

    # --------------------------------------------------------
    # PRODUCTS
    # --------------------------------------------------------

    category_map = {
        "electronics": "Electronics",
        "elec": "Electronics",
        "home & kitchen": "Home & Kitchen",
        "home and kitchen": "Home & Kitchen",
        "books": "Books",
        "book": "Books",
        "groceries": "Groceries",
        "grocery": "Groceries",
        "toys": "Toys",
        "toy": "Toys",
        "beauty": "Beauty",
        "beauty & care": "Beauty",
        "fashion": "Fashion",
        "fashon": "Fashion",
        "sports": "Sports",
        "sports & outdoor": "Sports",
    }

    products["category_clean"] = (
        products["category"]
        .astype("string")
        .str.strip()
        .str.lower()
        .replace(category_map)
        .fillna("Unknown")
    )

    products["unit_cost_clean"] = clean_money(
        products["unit_cost"]
    )

    products["list_price_clean"] = clean_money(
        products["unit_price"]
    )

    products["stock_qty_clean"] = pd.to_numeric(
        products["stock_qty"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # ORDERS
    # --------------------------------------------------------

    orders["order_date"] = pd.to_datetime(
        orders["order_datetime"],
        format="mixed",
        errors="coerce",
    )

    orders["discount_pct_clean"] = pd.to_numeric(
        orders["discount_pct"],
        errors="coerce",
    ).fillna(0)

    orders.loc[
        ~orders["discount_pct_clean"].between(
            0,
            1,
        ),
        "discount_pct_clean",
    ] = 0

    orders["shipping_fee_clean"] = clean_money(
        orders["shipping_fee"]
    ).fillna(0)

    # Referential integrity: valid customer
    orders = orders[
        orders["customer_id"].isin(
            customers["customer_id"]
        )
    ].copy()

    # --------------------------------------------------------
    # ORDER ITEMS
    # --------------------------------------------------------

    items["quantity_clean"] = pd.to_numeric(
        items["quantity"],
        errors="coerce",
    )

    items["unit_price_clean"] = clean_money(
        items["unit_price_at_purchase"]
    )

    items = items[
        (items["quantity_clean"] > 0)
        & items["unit_price_clean"].notna()
        & items["product_id"].isin(
            products["product_id"]
        )
        & items["order_id"].isin(
            orders["order_id"]
        )
    ].copy()

    # --------------------------------------------------------
    # SALES ANALYSIS - ITEM LEVEL
    # --------------------------------------------------------

    sales_all = (
        items
        .merge(
            orders[
                [
                    "order_id",
                    "customer_id",
                    "order_date",
                    "order_status",
                    "sales_channel",
                    "shipping_method",
                    "discount_pct_clean",
                    "shipping_fee_clean",
                ]
            ],
            on="order_id",
            how="inner",
            validate="many_to_one",
        )
        .merge(
            products[
                [
                    "product_id",
                    "product_name",
                    "brand",
                    "category_clean",
                    "unit_cost_clean",
                    "list_price_clean",
                    "stock_qty_clean",
                ]
            ],
            on="product_id",
            how="inner",
            validate="many_to_one",
        )
        .merge(
            customers[
                [
                    "customer_id",
                    "customer_name",
                    "gender_clean",
                    "age_clean",
                    "region_name",
                    "city",
                    "barangay",
                    "loyalty_tier",
                ]
            ],
            on="customer_id",
            how="left",
            validate="many_to_one",
        )
    )

    sales_all["gross_sales"] = (
        sales_all["quantity_clean"]
        * sales_all["unit_price_clean"]
    )

    sales_all["net_sales"] = (
        sales_all["gross_sales"]
        * (
            1
            - sales_all["discount_pct_clean"]
        )
    )

    sales_all["discount_amount"] = (
        sales_all["gross_sales"]
        - sales_all["net_sales"]
    )

    sales_all["estimated_cost"] = (
        sales_all["quantity_clean"]
        * sales_all["unit_cost_clean"]
    )

    sales_all["estimated_profit"] = (
        sales_all["net_sales"]
        - sales_all["estimated_cost"]
    )

    sales_all["month"] = (
        sales_all["order_date"]
        .dt.to_period("M")
        .astype("string")
    )

    sales_all["weekday"] = (
        sales_all["order_date"]
        .dt.day_name()
    )

    sales_all["hour"] = (
        sales_all["order_date"]
        .dt.hour
    )

    # --------------------------------------------------------
    # PAYMENTS
    # --------------------------------------------------------

    payments["amount_paid_clean"] = clean_money(
        payments["amount_paid"]
    )

    payments["payment_date_clean"] = pd.to_datetime(
        payments["payment_date"],
        format="mixed",
        errors="coerce",
    )

    # --------------------------------------------------------
    # SHIPMENTS
    # --------------------------------------------------------

    shipments["ship_date_clean"] = pd.to_datetime(
        shipments["ship_date"],
        format="mixed",
        errors="coerce",
    )

    shipments["delivered_date_clean"] = pd.to_datetime(
        shipments["delivered_date"],
        format="mixed",
        errors="coerce",
    )

    shipments["delivery_days"] = (
        shipments["delivered_date_clean"]
        - shipments["ship_date_clean"]
    ).dt.days

    shipments.loc[
        shipments["delivery_days"] < 0,
        "delivery_days",
    ] = pd.NA

    # --------------------------------------------------------
    # RETURNS
    # --------------------------------------------------------

    returns["return_request_date_clean"] = pd.to_datetime(
        returns["return_request_date"],
        format="mixed",
        errors="coerce",
    )

    returns["refund_amount_clean"] = clean_money(
        returns["refund_amount"]
    ).fillna(0)

    returns["refunded_flag_clean"] = (
        returns["refunded_flag"]
        .astype("string")
        .str.strip()
        .str.title()
        .fillna("Unknown")
    )

    # --------------------------------------------------------
    # ORDER-LEVEL SUMMARY
    # --------------------------------------------------------

    order_summary = (
        sales_all
        .groupby(
            "order_id",
            as_index=False,
        )
        .agg(
            customer_id=("customer_id", "first"),
            customer_name=("customer_name", "first"),
            order_date=("order_date", "first"),
            order_status=("order_status", "first"),
            sales_channel=("sales_channel", "first"),
            shipping_method=("shipping_method", "first"),
            region_name=("region_name", "first"),
            city=("city", "first"),
            loyalty_tier=("loyalty_tier", "first"),
            discount_pct=(
                "discount_pct_clean",
                "first",
            ),
            shipping_fee=(
                "shipping_fee_clean",
                "first",
            ),
            gross_order_value=(
                "gross_sales",
                "sum",
            ),
            net_order_value=(
                "net_sales",
                "sum",
            ),
            discount_amount=(
                "discount_amount",
                "sum",
            ),
            estimated_cost=(
                "estimated_cost",
                "sum",
            ),
            estimated_profit=(
                "estimated_profit",
                "sum",
            ),
            units=("quantity_clean", "sum"),
            line_items=("order_item_id", "nunique"),
        )
    )

    order_summary["profit_margin_pct"] = (
        order_summary["estimated_profit"]
        / order_summary["net_order_value"]
        * 100
    )

    order_summary["month"] = (
        order_summary["order_date"]
        .dt.to_period("M")
        .astype("string")
    )

    order_summary["weekday"] = (
        order_summary["order_date"]
        .dt.day_name()
    )

    order_summary["hour"] = (
        order_summary["order_date"]
        .dt.hour
    )

    clean_counts = {
        "Customers": len(customers),
        "Products": len(products),
        "Orders": len(orders),
        "Order Items": len(items),
        "Payments": len(payments),
        "Shipments": len(shipments),
        "Returns": len(returns),
    }

    return {
        "customers": customers,
        "products": products,
        "fsales_all": sales_all,
        "order_summary": order_summary,
        "payments": payments,
        "shipments": shipments,
        "returns": returns,
        "raw_counts": raw_counts,
        "clean_counts": clean_counts,
        "orders" : orders,
        "items" : items,
    }


# ============================================================
# 5. LOAD DATA
# ============================================================

try:
    data = load_data()

except FileNotFoundError as error:
    st.error(
        "One or more retail CSV files could not be found."
    )
    st.exception(error)
    st.stop()


customers = data["customers"]
products = data["products"]
sales_all = data["fsales_all"]
order_summary = data["order_summary"]
payments = data["payments"]
shipments = data["shipments"]
returns = data["returns"]
raw_counts = data["raw_counts"]
clean_counts = data["clean_counts"]
orders = data["orders"]
items = data["items"]

# ============================================================
# 6. FILTER STATE
# ============================================================

date_series = sales_all["order_date"].dropna()

min_date = date_series.min().date()
max_date = date_series.max().date()

all_regions = sorted(
    sales_all["region_name"]
    .dropna()
    .unique()
    .tolist()
)

all_channels = sorted(
    sales_all["sales_channel"]
    .dropna()
    .unique()
    .tolist()
)

all_categories = sorted(
    sales_all["category_clean"]
    .dropna()
    .unique()
    .tolist()
)

all_shipping_methods = sorted(
    sales_all["shipping_method"]
    .dropna()
    .unique()
    .tolist()
)


def reset_filters():
    st.session_state["date_range"] = (
        min_date,
        max_date,
    )
    st.session_state["regions"] = all_regions
    st.session_state["channels"] = all_channels
    st.session_state["categories"] = all_categories
    st.session_state["shipping_methods"] = all_shipping_methods


if "date_range" not in st.session_state:
    reset_filters()

# ============================================================
# 7. SIDEBAR
# ============================================================

with st.sidebar:
    st.header("Dashboard Filters")
    st.caption(
        "Filters apply across all analytical sections."
    )

    selected_dates = st.date_input(
        "Order date range",
        min_value=min_date,
        max_value=max_date,
        key="date_range",
    )

    if isinstance(selected_dates, (tuple, list)):
        if len(selected_dates) == 2:
            start_date = selected_dates[0]
            end_date = selected_dates[1]
        else:
            start_date = min_date
            end_date = max_date
    else:
        start_date = selected_dates
        end_date = selected_dates

    selected_regions = st.multiselect(
        "Region",
        all_regions,
        key="regions",
    )

    selected_channels = st.multiselect(
        "Sales Channel",
        all_channels,
        key="channels",
    )

    selected_categories = st.multiselect(
        "Product Category",
        all_categories,
        key="categories",
    )

    selected_shipping = st.multiselect(
        "Shipping Method",
        all_shipping_methods,
        key="shipping_methods",
    )

    st.button(
        "Reset Filters",
        width="stretch",
        type="primary",
        on_click=reset_filters,
    )

    st.divider()

    st.caption(
        "Sales KPIs use fulfilled orders: Completed + Shipped."
    )

# ============================================================
# 8. FILTER ANALYTICAL DATA
# ============================================================

filtered_all = filter_sales(
    sales_all,
    start_date,
    end_date,
    selected_regions,
    selected_channels,
    selected_categories,
    selected_shipping,
)

if filtered_all.empty:
    st.warning(
        "No records match the selected filters."
    )
    st.stop()


filtered_fulfilled = filtered_all[
    filtered_all["order_status"].isin(
        [
            "Completed",
            "Shipped",
        ]
    )
].copy()

matching_all_order_ids = (
    filtered_all["order_id"]
    .drop_duplicates()
    .tolist()
)

matching_fulfilled_order_ids = (
    filtered_fulfilled["order_id"]
    .drop_duplicates()
    .tolist()
)

filtered_orders_all = order_summary[
    order_summary["order_id"].isin(
        matching_all_order_ids
    )
].copy()

filtered_orders_fulfilled = order_summary[
    order_summary["order_id"].isin(
        matching_fulfilled_order_ids
    )
].copy()

payment_scope = payments[
    payments["order_id"].isin(
        matching_all_order_ids
    )
].copy()

shipment_scope = shipments[
    shipments["order_id"].isin(
        matching_all_order_ids
    )
].copy()

return_scope = returns[
    returns["order_id"].isin(
        matching_all_order_ids
    )
].copy()

# ============================================================
# 9. HEADER
# ============================================================

st.markdown(
    """
    <div class="hero">
        <div class="hero-title">
            📊 Sales Performance & Customer Insights
        </div>
        <div class="hero-sub">
            An overview of sales performance, revenue growth,
            and customer purchasing patterns.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

make_filter_chips(
    start_date,
    end_date,
    selected_regions,
    selected_channels,
    selected_categories,
)

# ============================================================
# 10. EXECUTIVE KPI STRIP
# ============================================================

gross_sales = filtered_fulfilled["gross_sales"].sum()
net_sales = filtered_fulfilled["net_sales"].sum()
discount_value = filtered_fulfilled["discount_amount"].sum()
estimated_profit = filtered_fulfilled["estimated_profit"].sum()
units_sold = filtered_fulfilled["quantity_clean"].sum()
fulfilled_orders = filtered_fulfilled["order_id"].nunique()
unique_customers = filtered_fulfilled["customer_id"].nunique()

aov = (
    filtered_orders_fulfilled["net_order_value"].mean()
    if not filtered_orders_fulfilled.empty
    else 0
)

profit_margin = (
    estimated_profit / net_sales * 100
    if net_sales != 0
    else 0
)

k1, k2, k3, k4, k5 = st.columns(5, border=False)


k1.metric(
    "Total Revenue",
    f"₱{compact_number(gross_sales)}",
)

k2.metric(
    "Total Orders",
    f"{fulfilled_orders:,}",
)

k3.metric(
    "Average Order Value",
    f"₱{aov:,.2f}",
)

k4.metric(
    "Profit/Loss",
    f"₱{compact_number(estimated_profit)}",
)

k5.metric(
    "Profit Margin",
    f"{profit_margin:.1f}%",
)

# --------------------------------------------------------
# Monthly revenue trend
# --------------------------------------------------------

monthly_revenue = (
    filtered_fulfilled
    .groupby(
        "month",
        as_index=False,
    )
    .agg(
        Gross_Sales=("gross_sales", "sum"),
    )
    .sort_values("month")
)

max_revenue = monthly_revenue["Gross_Sales"].max()
y_max = max_revenue * 1.20
y_interval = 25000

fig = px.line(
    monthly_revenue,
    x="month",
    y=[
        "Gross_Sales",
    ],
    markers=True,
    title="How has monthly revenue trended over time?",
    labels={
        "month": "Month",
        "value": "Sales (PHP)",
        "variable": "Measure",
    },
    color_discrete_sequence=[
        BLUE,
    ],
)

fig.update_layout(
xaxis_title=None,
yaxis_title=None,
legend_title_text=None,
showlegend=False,
hovermode="x unified",
)

fig.update_yaxes(
range=[0, y_max],
dtick=50000,
tickprefix="₱",
tickformat="~s",
)

chart_card(
    style_figure(
        fig,
        height=440,
    )
)

left, right = st.columns(
    2,
    gap="medium",
)

# ------------------------------------------------------------
# TOP 10 PRODUCTS
# ------------------------------------------------------------

with left:

    with st.container(border=True):

        # 1. Aggregate gross sales by product
        top_products = (
            filtered_fulfilled
            .dropna(subset=["product_name"])
            .groupby("product_name", as_index=False)
            .agg(
                gross_sales=("gross_sales", "sum")
            )
            .nlargest(10, "gross_sales")
            .sort_values("gross_sales", ascending=False)
        )

        # 2. Highlight highest-revenue product
        highest_product = (
            top_products.loc[
                top_products["gross_sales"].idxmax(),
                "product_name"
            ]
            if not top_products.empty else None
        )

        product_colors = [
            "#0247B7" if product == highest_product else "#93C5FD"
            for product in top_products["product_name"]
        ]

        # 3. Create horizontal bar chart
        fig_product = px.bar(
            top_products,
            x="gross_sales",
            y="product_name",
            orientation="h",
            color="product_name",
            color_discrete_map={
                product: product_colors[i]
                for i, product in enumerate(top_products["product_name"])
            },
            labels={
                "gross_sales": "",
                "product_name": "",
            },
            title="Which products are performing best?",
        )

        # 4. Customize chart appearance
        fig_product.update_layout(
            height=450,
            template="plotly_white",
            margin=dict(l=20, r=20, t=60, b=40),
            showlegend=False,
            xaxis=dict(
                title="",
                tickprefix="₱",
                tickformat="~s",
                showticklabels=True,
                showgrid=False,
                zeroline=False,
                showline=False,
            ),
            yaxis=dict(
                title="",
                showgrid=False,
                zeroline=False,
                showline=False,
            ),
        )

        # 5. Display chart
        if not top_products.empty:
            st.plotly_chart(
                fig_product,
                width="stretch",
            )
        else:
            st.warning("No product sales data available.")


# ------------------------------------------------------------
# REVENUE BY REGION
# ------------------------------------------------------------

with right:

    with st.container(border=True):

        # 1. Aggregate gross sales by all regions
        region_sales = (
            filtered_fulfilled
            .dropna(subset=["region_name"])
            .groupby("region_name", as_index=False)
            .agg(
                gross_sales=("gross_sales", "sum")
            )
            .sort_values("gross_sales", ascending=False)
        )

        # 2. Highlight the highest-revenue region
        highest_region = (
            region_sales.loc[
                region_sales["gross_sales"].idxmax(),
                "region_name"
            ]
            if not region_sales.empty else None
        )

        region_colors = [
            "#0247B7" if region == highest_region else "#93C5FD"
            for region in region_sales["region_name"]
        ]

        # 3. Create horizontal bar chart
        fig_region = px.bar(
            region_sales,
            x="gross_sales",
            y="region_name",
            orientation="h",
            color="region_name",
            color_discrete_map={
                region: region_colors[i]
                for i, region in enumerate(region_sales["region_name"])
            },
            labels={
                "gross_sales": "Gross Sales (PHP)",
                "region_name": "",
            },
            title="How is revenue distributed across regions?",
        )

        # 4. Set X-axis maximum based on highest revenue
        if not region_sales.empty:
            max_revenue = region_sales["gross_sales"].max()
            x_max = max_revenue * 1.05
        else:
            x_max = 0

        # 5. Customize chart appearance
        fig_region.update_layout(
            height=450,
            template="plotly_white",
            margin=dict(l=20, r=20, t=60, b=40),
            showlegend=False,
            xaxis=dict(
                title="",
                range=[0, x_max] if x_max > 0 else None,
                showticklabels=True,
                tickprefix="₱",
                tickformat="~s",
                showgrid=False,
                zeroline=False,
                showline=False,
            ),
            yaxis=dict(
                title="",
                showgrid=False,
                zeroline=False,
                showline=False,
            ),
        )

        # 6. Display chart
        if not region_sales.empty:
            st.plotly_chart(
                fig_region,
                width="stretch",
            )
        else:
            st.warning("No regional sales data available.")



# --------------------------------------------------------
# REPEAT VS NEW CUSTOMERS
# --------------------------------------------------------

with left:

    with st.container(border=True, height=450):

        customer_orders = (
            filtered_fulfilled
            .groupby("customer_id")["order_id"]
            .nunique()
            .reset_index(name="total_orders")
        )

        customer_orders["customer_type"] = customer_orders[
            "total_orders"
        ].apply(
            lambda x: "Repeat Customer" if x > 1 else "New Customer"
        )

        customer_summary = (
            customer_orders["customer_type"]
            .value_counts()
            .reset_index()
        )

        customer_summary.columns = [
            "customer_type",
            "customer_count"
        ]

        fig = px.pie(
            customer_summary,
            names="customer_type",
            values="customer_count",
            title="What is the share of new vs. returning customers?",
            hole=0.4
        )

        fig.update_layout(
            height=425,
            legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.15,
            xanchor="center",
            x=0.5
            )
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

# --------------------------------------------------------
# CUSTOMER SPENDING
# --------------------------------------------------------

with right:

    with st.container(border=True, height=450):

        customer_spending = (
            filtered_fulfilled
            .groupby("customer_id", as_index=False)["gross_sales"]
            .sum()
            .rename(columns={"gross_sales": "customer_spend"})
        )

        fig = px.histogram(
            customer_spending,
            x="customer_spend",
            nbins=30,
            title="How much do customers spend?",
            labels={
                "customer_spend": ""
            }
        )

        fig.update_layout(
            height=425
        )

        # Add Peso sign to X-axis
        fig.update_xaxes(
            tickprefix="₱"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )


# --------------------------------------------------------
# ORDER CANCELLATIONS ANALYSIS
# --------------------------------------------------------

with st.container(border=True):

    orders_analysis = orders.copy()

    # Convert order date
    orders_analysis["order_date"] = pd.to_datetime(
        orders_analysis["order_date"],
        errors="coerce"
    )

    # Identify cancelled orders
    orders_analysis["is_cancelled"] = (
        orders_analysis["order_status"]
        .astype(str)
        .str.contains("cancel", case=False, na=False)
    )

    # Remove missing dates
    orders_analysis = orders_analysis.dropna(
        subset=["order_date"]
    )

    # Apply dashboard date filter
    orders_analysis = orders_analysis[
        orders_analysis["order_date"].dt.date.between(
            start_date,
            end_date
        )
    ].copy()

    # Extract month
    orders_analysis["month"] = (
        orders_analysis["order_date"]
        .dt.to_period("M")
        .astype(str)
    )

    # Monthly cancellation summary
    cancellation_trend = (
        orders_analysis
        .groupby("month")
        .agg(
            total_orders=("order_id", "nunique"),
            cancelled_orders=("is_cancelled", "sum")
        )
        .reset_index()
    )

    # Calculate cancellation rate
    all_orders = orders_analysis["order_id"].nunique()

    cancelled_orders = orders_analysis.loc[
        orders_analysis["is_cancelled"], "order_id"
    ].nunique()

    cancellation_rate = (
        cancelled_orders / all_orders * 100
        if all_orders > 0 else 0
    )

    # Create line chart
    fig = px.line(
        cancellation_trend,
        x="month",
        y="cancelled_orders",
        markers=True,
        title="How is the monthly order cancellation trend?",
        labels={
            "month": "",
            "cancelled_orders": ""
        }
    )

    # Remove X-axis gridlines
    fig.update_xaxes(
        showgrid=False
    )

    # Show Y-axis gridlines only
    fig.update_yaxes(
        showgrid=True,
        gridcolor="#E5E7EB",
        gridwidth=1,
        rangemode="tozero"
    )

    # Keep lines and markers, remove data labels
    fig.update_traces(
        mode="lines+markers"
    )

    # Cancellation rate at upper right
    fig.add_annotation(
        x=1,
        y=1.18,
        xref="paper",
        yref="paper",
        text=(
            f"<b>Cancellation Rate</b><br><br>"
            f"<span style='font-size:24px'>{cancellation_rate:.2f}%</span>"
        ),
        showarrow=False,
        align="right",
        xanchor="right",
        yanchor="top"
    )

    # Chart layout
    fig.update_layout(
        margin=dict(t=100, r=30, b=40, l=40)
    )

    # Display chart
    st.plotly_chart(
        fig,
        use_container_width=True
    )


