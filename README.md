markdownCopy# Climate Platform

A web-based platform for analyzing global temperature data using Google Earth Engine, CMIP6 projections, and historical observations.

## Features

- Interactive map-based temperature analysis
- CMIP6 multi-model ensemble visualization
- Historical GLDAS data comparison
- Ensemble statistics and uncertainty visualization
- Data export capabilities

## Installation

1. Clone the repository:
```bash
git clone https://github.com/DarriEy/Climate_Platform.git
cd Climate_Platform
```

Create and activate a virtual environment:

```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install dependencies:

```
pip install -r requirements.txt
```

Set up Earth Engine authentication:

```
earthengine authenticate
```

## Usage

Run the Streamlit app:
```
streamlit run src/app.py
```

Visit http://localhost:8501 in your web browser.

## Documentation
See the docs directory for detailed documentation.

##  Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
