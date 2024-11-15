# app.py
import streamlit as st
import plotly.express as px
from temperature_analyzer import TemperatureAnalyzer
import folium
from streamlit_folium import st_folium

# Initialize session state for caching
if 'analyzer' not in st.session_state:
    st.session_state.analyzer = None
if 'last_params' not in st.session_state:
    st.session_state.last_params = None

st.set_page_config(page_title="Temperature Analysis", layout="wide")
st.title("Global Temperature Analysis")

# Sidebar controls
st.sidebar.header("Settings")
start_year = st.sidebar.slider("Start Year", 2010, 2020, 2010)
end_year = st.sidebar.slider("End Year", 2021, 2050, 2050)
scenario = st.sidebar.selectbox(
    "CMIP6 Scenario",
    ["ssp126", "ssp245", "ssp370", "ssp585"],
    index=3
)

# Check if we need to reinitialize the analyzer
current_params = (start_year, end_year, scenario)
if st.session_state.last_params != current_params:
    st.session_state.analyzer = TemperatureAnalyzer(start_year, end_year, scenario)
    st.session_state.last_params = current_params

# Cache the map
@st.cache_data
def get_base_map():
    return folium.Map(location=[0, 0], zoom_start=2)

st.write("Click on the map to select a location:")
map_data = st_folium(get_base_map(), height=400)

if map_data['last_clicked']:
    lat = map_data['last_clicked']['lat']
    lon = map_data['last_clicked']['lng']
    
    # Get temperature data with progress
    with st.spinner("Fetching temperature data..."):
        # Cache key for this location and parameters
        cache_key = st.session_state.analyzer._generate_cache_key(
            lat, lon, 
            start_year=start_year,
            end_year=end_year,
            scenario=scenario
        )
        
        # Check cache first
        @st.cache_data(ttl=3600)  # Cache for 1 hour
        def get_cached_data(cache_key):
            return st.session_state.analyzer.get_point_data(lat, lon)
        
        data = get_cached_data(cache_key)
        
        # Format data for plotting
        @st.cache_data
        def get_formatted_data(data_str):
            return st.session_state.analyzer.format_data_for_plotting(data_str)
        
        df = get_formatted_data(str(data))

    # Plot with caching
    @st.cache_data
    def create_plot(df, lat, lon):
        # Create figure with secondary y-axis
        fig = px.line(df, x='date', y=['GLDAS'], 
                     title=f"Temperature at {lat:.2f}°N, {lon:.2f}°E",
                     labels={'value': 'Temperature (°C)',
                            'variable': 'Dataset'})
        
        # Update GLDAS line style
        fig.update_traces(line=dict(color='blue', width=3), name='GLDAS (Historical)')
        
        # Add CMIP6 model lines
        cmip6_cols = [col for col in df.columns if col.startswith('CMIP6_') 
                     and not col.startswith('CMIP6_std')
                     and not col.endswith(('mean', 'upper', 'lower'))]
        
        for col in cmip6_cols:
            fig.add_scatter(x=df['date'], y=df[col],
                          name=col.replace('CMIP6_', ''),
                          line=dict(color='red', width=0.5, opacity=0.3),
                          showlegend=True)
        
        # Add ensemble mean and confidence interval
        fig.add_scatter(x=df['date'], y=df['CMIP6_mean'],
                       name='CMIP6 Ensemble Mean',
                       line=dict(color='red', width=2),
                       showlegend=True)
        
        fig.add_scatter(x=df['date'], y=df['CMIP6_upper'],
                       name='95% Confidence Interval',
                       line=dict(color='red', width=0),
                       showlegend=False)
        
        fig.add_scatter(x=df['date'], y=df['CMIP6_lower'],
                       name='95% Confidence Interval',
                       fill='tonexty',
                       fillcolor='rgba(255,0,0,0.2)',
                       line=dict(color='red', width=0),
                       showlegend=False)
        
        # Update layout
        fig.update_layout(
            yaxis_title='Temperature (°C)',
            xaxis_title='Date',
            hovermode='x unified',
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            )
        )
        
        return fig
    
    # Display statistics with caching
    @st.cache_data
    def calculate_stats(df):
        cmip6_cols = [col for col in df.columns if col.startswith('CMIP6_') 
                     and not col.startswith('CMIP6_std')
                     and not col.endswith(('mean', 'upper', 'lower'))]
        
        return {
            'gldas_mean': df['GLDAS'].mean(),
            'cmip6_ensemble_mean': df['CMIP6_mean'].mean(),
            'model_count': len(cmip6_cols),
            'ensemble_spread': df['CMIP6_std'].mean()
        }
    
    stats = calculate_stats(df)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("GLDAS Mean", f"{stats['gldas_mean']:.1f}°C")
    with col2:
        st.metric("CMIP6 Ensemble Mean", f"{stats['cmip6_ensemble_mean']:.1f}°C")
    with col3:
        st.metric("Number of Models", f"{stats['model_count']}")
    with col4:
        st.metric("Ensemble Spread", f"±{stats['ensemble_spread']:.1f}°C")

    # Add download button for the data
    @st.cache_data
    def convert_df_to_csv(df):
        return df.to_csv().encode('utf-8')

    csv = convert_df_to_csv(df)
    st.download_button(
        "Download Data as CSV",
        csv,
        "temperature_data.csv",
        "text/csv",
        key='download-csv'
    )