# temperature_analyzer.py
import ee
import pandas as pd
import datetime
from typing import Dict, List, Tuple
from functools import lru_cache
import hashlib
import json

class TemperatureAnalyzer:
    def __init__(self, start_year: int = 2010, end_year: int = 2050, scenario: str = 'ssp585'):
        """Initialize the analyzer with time range and scenario."""
        ee.Initialize()
        
        self.start_year = start_year
        self.end_year = end_year
        self.scenario = scenario
        self.historical_cutoff = 2022
        self.cmip6_transition = 2015
        
        # Initialize and cache datasets
        self._init_datasets()

    def _init_datasets(self):
        """Initialize and cache the filtered datasets."""
        self.gldas = ee.ImageCollection("NASA/GLDAS/V021/NOAH/G025/T3H")
        self.cmip6 = ee.ImageCollection("NASA/GDDP-CMIP6")
        
        # Pre-filter datasets by date range
        self.start_date = ee.Date.fromYMD(self.start_year, 1, 1)
        self.end_date = ee.Date.fromYMD(self.end_year, 12, 31)
        self.historical_end = ee.Date.fromYMD(min(self.historical_cutoff, self.end_year), 12, 31)
        
        # Cache the filtered collections
        self.filtered_gldas = self.gldas.select('Tair_f_inst').filterDate(self.start_date, self.historical_end)
        self.filtered_cmip6 = (self.cmip6
            .select('tas')
            .filter(ee.Filter.eq('scenario', self.scenario))
            .filterDate(self.start_date, self.end_date))

    @staticmethod
    def _generate_cache_key(lat: float, lon: float, **kwargs) -> str:
        """Generate a unique cache key based on parameters."""
        params = {
            'lat': round(lat, 4),
            'lon': round(lon, 4),
            **kwargs
        }
        key = json.dumps(params, sort_keys=True)
        return hashlib.md5(key.encode()).hexdigest()

    @lru_cache(maxsize=128)
    def get_point_data_cached(self, cache_key: str) -> Dict:
        """Cached version of point data retrieval."""
        # Parse lat/lon from cache_key
        params = json.loads(cache_key)
        point = ee.Geometry.Point(params['lon'], params['lat'])

        gldas_data = self.filtered_gldas.filterBounds(point)
        cmip6_data = self.filtered_cmip6.filterBounds(point)

        # Calculate monthly averages
        gldas_monthly = self._calculate_monthly_average(gldas_data, point, 'Tair_f_inst')
        cmip6_monthly = self._calculate_monthly_average(cmip6_data, point, 'tas')

        return {
            'gldas': gldas_monthly.getInfo(),
            'cmip6': cmip6_monthly.getInfo(),
            'metadata': {
                'lat': params['lat'],
                'lon': params['lon'],
                'scenario': self.scenario
            }
        }

    def get_point_data(self, lat: float, lon: float) -> Dict:
        """Get data for all CMIP6 models at a point."""
        cache_key = self._generate_cache_key(lat, lon, 
                                           start_year=self.start_year,
                                           end_year=self.end_year,
                                           scenario=self.scenario)
        
        point = ee.Geometry.Point(lon, lat)
        
        # Get GLDAS data as before
        gldas_data = self.filtered_gldas.filterBounds(point)
        gldas_monthly = self._calculate_monthly_average(gldas_data, point, 'Tair_f_inst')

        # Get all unique CMIP6 models
        models = self.filtered_cmip6.distinct('model').aggregate_array('model').getInfo()
        
        # Get data for each model
        cmip6_by_model = {}
        for model in models:
            model_data = (self.filtered_cmip6
                .filter(ee.Filter.eq('model', model))
                .filterBounds(point))
            cmip6_by_model[model] = self._calculate_monthly_average(model_data, point, 'tas')

        return {
            'gldas': gldas_monthly.getInfo(),
            'cmip6_models': {model: data.getInfo() for model, data in cmip6_by_model.items()},
            'metadata': {
                'lat': lat,
                'lon': lon,
                'scenario': self.scenario,
                'models': models
            }
        }

    @staticmethod
    @lru_cache(maxsize=128)
    def _calculate_monthly_average(collection, point, band_name: str) -> ee.List:
        """Cached version of monthly average calculation."""
        def monthly_reducer(image):
            value = image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point,
                scale=25000
            ).get(band_name)
            
            temp_c = ee.Number(value).subtract(273.15)
            
            return ee.Feature(None, {
                'temperature': temp_c,
                'date': image.date().format('YYYY-MM')
            })

        return collection.map(monthly_reducer).aggregate_array('temperature')

    @lru_cache(maxsize=128)
    def format_data_for_plotting(self, data_key: str) -> pd.DataFrame:
        """Format data including all CMIP6 models."""
        raw_data = json.loads(data_key)
        dates = pd.date_range(
            start=f"{self.start_year}-01-01",
            end=f"{self.end_year}-12-31",
            freq='M'
        )

        # Start with GLDAS data
        df = pd.DataFrame({
            'date': dates,
            'GLDAS': raw_data['gldas'][:len(dates)]
        })

        # Add each CMIP6 model
        for model, data in raw_data['cmip6_models'].items():
            df[f'CMIP6_{model}'] = data[:len(dates)]

        # Calculate ensemble statistics
        cmip6_cols = [col for col in df.columns if col.startswith('CMIP6_')]
        df['CMIP6_mean'] = df[cmip6_cols].mean(axis=1)
        df['CMIP6_std'] = df[cmip6_cols].std(axis=1)
        df['CMIP6_upper'] = df['CMIP6_mean'] + 2 * df['CMIP6_std']
        df['CMIP6_lower'] = df['CMIP6_mean'] - 2 * df['CMIP6_std']

        return df