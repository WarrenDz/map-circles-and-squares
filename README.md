# MapCirclesAndSquares
Python geoprocessing toolbox for creating map based packed circles and treemaps in ArcGIS Pro.
 
## Contents
- [Installation](https://github.com/WarrenDz/MapCharts#installation)
- [Usage](https://github.com/WarrenDz/MapCharts#usage)
- [Documentation](https://github.com/WarrenDz/MapCharts#documentation)

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

Install [circlify](https://github.com/elmotec/circlify) used to create packed circles with hierarchy.

    `pip install circlify`

Install [packcircles](https://github.com/mhtchan/packcircles) used to create packed circles with a flat hierarchy (clustered circles).

    `pip install packedcircles`

## Usage
The following describes the various inputs and outputs of each tool within the toolbox.

### Create Flat Packed Map Circles


`in_fc`: The input feature class or layer.

`out_fc`: The output feature class that will be created and to which the results will be written.

`value`: Specifies the numeric field containing the attribute values that will be used to scale the area of each proportional circle. Null values are excluded from the calculations.

`group_field`: The field in the input that will be used to geographically aggregate features. Features within each group will have their coordinates averaged to determine the centroid of the packed circle.

Suggested values might included administrative areas such as, neighborhoods, states/provinces, and countries.

`sort_field` (optional): Specifies the field whose values will be used to reorder the input records.

`sort_dir`: Specifies the direction the records will be sorted.

- DEFAULT: The circles within each packed circle will be arranged from the centroid outwards (counter-clockwise) in the order they enter the tool.

- ASCENDING: The circles within each packed circle will be arranged from the centroid outwards (counter-clockwise) in ascending order of the values of the features.

- DSCEDNING: The circles within each packed circle will be arranged from the centroid outwards (counter-clockwise) in descending order of the values of the features.

- RANDOM: The circles within each packed circle will be randomly arranged from the centroid outwards (counter-clockwise). Repeat iteration of the tool will not be identical.

`diam_min`: A numerical constraint that will be used to determine the minimum proportional circle symbol diameter. The area of the circle symbols will be scaled proportionally based on their data value.

This measurement uses the units of the input feature coordinate system and may require some experimentation to achieve the desired effect.

`diam_max`: A numerical constraint that will be used to determine the maximum proportional circle symbol diameter. The area of the circle symbols will be scaled proportionally based on their data value.

This measurement uses the units of the input feature coordinate system and may require some experimentation to achieve the desired effect.

### Create Map Treemaps


`in_fc`: The input feature class or layer.

`out_fc`: The output feature class that will be created and to which the results will be written.

`value`: Specifies the numeric field containing the attribute values that will be used to apportion the area of each segment of the treemap and the size of the proportional treemap symbols. Null values are excluded from the calculations.

`group_field`: An attribute field from the input summary features that is used for grouping. Coordinates of features that have the same group field value will be averaged to determine the centroid of the treemap features. The sum of numeric values within the group will determine the scaling of the proportional treemap feature.

Suggested values might included administrative areas such as, neighborhoods, states/provinces, and countries.

`case_field`: The field or fields in the input that will be used to calculate statistics separately for each unique attribute value (or combination of attribute values when multiple fields are specified).

`width_min`: A numerical constraint that will be used to determine the minimum proportional treemap symbol width. The area of the treemap symbols will be scaled proportionally based on the aggregated data values within the group.

This measurement uses the units of the input feature coordinate system and may require some experimentation to achieve the desired effect.

`width_max`: A numerical constraint that will be used to determine the maximum proportional treemap symbol width. The area of the treemap symbols will be scaled proportionally based on the aggregated data values within the group.

This measurement uses the units of the input feature coordinate system and may require some experimentation to achieve the desired effect.

### Create Map Packed Circles


`in_fc`: The input feature class or layer.

`out_fc`: The output feature class that will be created and to which the results will be written.

`value`: Specifies the numeric field containing the attribute values that will be used to apportion the area of each segment of the treemap and the size of the proportional treemap symbols. Null values are excluded from the calculations.

`group_field`: An attribute field from the input summary features that is used for grouping. Coordinates of features that have the same group field value will be averaged to determine the centroid of the packed circle features. The sum of numeric values within the group will determine the scaling of the proportional packed circle feature.

Suggested values might included administrative areas such as, neighborhoods, states/provinces, and countries.

`case_field`: The field in the input that will be used to aggregate data within geographic groupings. This field also determines hierarchical grouping of circles.

`category_field`: The field in the input that will be used to calculate statistics separately for each unique attribute value. This field represents the lowest level of granularity within the data.

`width_min`: A numerical constraint that will be used to determine the minimum proportional packed circle symbol width. The area of the packed circle will be scaled proportionally based on the aggregated data values within the group.

This measurement uses the units of the input feature coordinate system and may require some experimentation to achieve the desired effect.

`width_max`: A numerical constraint that will be used to determine the maximum proportional packed circle symbol width. The area of the packed circle will be scaled proportionally based on the aggregated data values within the group.

This measurement uses the units of the input feature coordinate system and may require some experimentation to achieve the desired effect.

## Documention
Some things to remember and some known issues
- **These tools calculate sizes in the units of the coordinate system of the input layer**.
- An **equal area** projection should be used when running these tools and visualizing the outputs.
- The most common error is `The coordinates or measures are out of bounds.` this happens when the allowable size of the output features exceeds the bounds of the coordinate system being used. You'll need to change your coordinate system or reduce the allowable size of the output features.
