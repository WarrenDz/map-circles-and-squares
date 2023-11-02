# MapCharts
Python geoprocessing toolbox for creating map based charts in ArcGIS Pro.
 
## Contents
- Installation
- Usage
- Documentation

## Installation
The following steps outline how to download the toolbox and install the required Python packages.

### Toolbox
1. [Download](https://github.com/WarrenDz/MapCharts/archive/refs/heads/main.zip) and extract or clone this repo to a convenient location on your machine.
2. [Add the toolbox](https://pro.arcgis.com/en/pro-app/latest/help/analysis/geoprocessing/basics/use-a-custom-geoprocessing-tool.htm) to your ArcGIS Pro project.

### Python packages
1. [Clone your default ArcGIS Pro environment](https://pro.arcgis.com/en/pro-app/latest/arcpy/get-started/clone-an-environment.htm) and provide it a name.
2. In the new environment, run the following commands to install the required libraries.
Install [squarify](https://github.com/laserson/squarify) used to create treemaps.
`pip install squarify`
Install [circlify](https://github.com/elmotec/circlify/tree/main) used to create packed circles with hierarchy
`pip install circlify`
Install [packcircles](https://github.com/mhtchan/packcircles/tree/main) used to create packed circles with a flat hierarchy (clustered circles).
`pip install packedcircles`
