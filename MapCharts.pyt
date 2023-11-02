# ---------------------------------------------------------------------------
# MapCharts.pyt
# Purpose:      Creates packed circles and treemaps on a map
#
# Author:       Warren Davison
#
# Created:      6/27/2023
# ---------------------------------------------------------------------------

import arcpy
import os, math


class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Map Charts"
        self.alias = "toolbox"

        # List of tool classes associated with this toolbox
        self.tools = [MapTreemaps, FlatPackedMapCircles, PackCircleHierarchy]


class FlatPackedMapCircles(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Create Flat Packed Map Circles"
        self.description = "Geoprocessing tool that creates single hierarchy packed circles on a map based on a common geographic group attribute."
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Input features",
            name="in_fc",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
        param0.filter.list = ["Point"]
    
        param1 = arcpy.Parameter(
            displayName="Output Features",
            name="out_fc",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Output")

        param2 = arcpy.Parameter(
            displayName="Value",
            name="value",
            datatype="Field",
            parameterType="Required",
            direction="Input")
        param2.filter.list = ['Short', 'Long', 'Float', 'Double']
        param2.parameterDependencies = [param0.name]

        param3 = arcpy.Parameter(
            displayName="Geographic group field",
            name="group_field",
            datatype="Field",
            parameterType="Required",
            direction="Input")
        param3.filter.list = ['String', 'Short']
        param3.parameterDependencies = [param0.name]

        param4 = arcpy.Parameter(
            displayName="Sort field",
            name="sort_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input") 
        param4.filter.list = ['Short', 'Long', 'Float', 'Double', 'String']
        param4.parameterDependencies = [param0.name]

        param5 = arcpy.Parameter(
            displayName="Sort direction",
            name="sort_dir",
            datatype="String",
            parameterType="Optional",
            direction="Input")
        param5.filter.type = "ValueList"
        param5.filter.list = ['DEFAULT', 'ASCENDING', 'DESCENDING', 'RANDOM']
        param5.value = "DESCENDING"
        param5.parameterDependencies = [param4.name]
        param5.enabled = False

        param6 = arcpy.Parameter(
            displayName="Minimum symbol diameter",
            name="diam_min",
            datatype="Long",
            parameterType="Required",
            direction="Input")

        param7 = arcpy.Parameter(
            displayName="Maximum symbol diameter",
            name="diam_max",
            datatype="Long",
            parameterType="Required",
            direction="Input")

        params = [param0, param1, param2, param3, param4, param5, param6, param7]

        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        # Check the output path exists
        if parameters[1].altered:
            if parameters[1].value:
                outPath, outName =os.path.split(parameters[1].value.value)
                if not os.path.exists(outPath):
                    parameters[1].setErrorMessage('Output path does not exist.')
        
        # Only enable sort direction when sorting is not DEFAULT
        if parameters[4].altered and parameters[4] != "":
            if parameters[4].value:
                parameters[5].enabled = True
            else:
                parameters[5].enabled = False
        else:
            parameters[5].enabled = False

        # Check to make sure that min/max diameters are logical
        if parameters[6].altered and parameters[7].altered:
            if parameters[6].value and parameters[7].value:
                if parameters[6].value >= parameters[7].value:
                    parameters[6].setErrorMessage('The minimum symbol diameter must be less than the maximum symbol diameter.')
                    parameters[7].setErrorMessage('The maximum symbol diameter must be greater than the minimum symbol diameter.')
                if parameters[6].value < 0:
                    parameters[6].setErrorMessage('The minimum symbol diameter must be greater than 0.')
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        import pandas as pd
        import packcircles as pc

        arcpy.env.overwriteOutput = True
        arcpy.addOutputsToMap = True

        # Containers to hold various things
        groups = []
        circles_list = []

        # Parameters
        in_fc = parameters[0].valueAsText
        out_fc = parameters[1].valueAsText
        measure_field = parameters[2].valueAsText
        group_field = parameters[3].valueAsText
        sort_field = parameters[4].valueAsText
        sort_dir = parameters[5].valueAsText
        diam_min = parameters[6].value
        diam_max = parameters[7].value

        arcpy.env.outputCoordinateSystem = arcpy.Describe(in_fc).spatialReference
        oid_field = arcpy.Describe(in_fc).OIDFieldName
        sr = arcpy.Describe(in_fc).spatialReference.exportToString()

        # Functionality: Convert feature class to pandas dataframe
        # Original Author: [d-wasserman](https://gist.github.com/d-wasserman)
        # Source: https://gist.github.com/d-wasserman/e9c98be1d0caebc2935afecf0ba239a0
        def arcgis_table_to_df(in_fc, input_fields=None, query=""):
            """Function will convert an arcgis table into a pandas dataframe with an object ID index, and the selected
            input fields using an arcpy.da.SearchCursor.
            :param - in_fc - input feature class or table to convert
            :param - input_fields - fields to input to a da search cursor for retrieval
            :param - query - sql query to grab appropriate values
            :returns - pandas.DataFrame"""
            OIDFieldName = arcpy.Describe(in_fc).OIDFieldName
            if input_fields:
                final_fields = [OIDFieldName] + input_fields
            else:
                final_fields = [field.name for field in arcpy.ListFields(in_fc)]

            data = [row for row in arcpy.da.SearchCursor(in_fc,final_fields,where_clause=query)]
            fc_dataframe = pd.DataFrame(data,columns=final_fields)
            # fc_dataframe = fc_dataframe.set_index(OIDFieldName,drop=False)
            return fc_dataframe

        def data_extents(df, field):
            data_max = df.max(axis=0, numeric_only=True)[field]
            data_min = df.min(axis=0, numeric_only=True)[field]
            return [data_min, data_max]

        def data_to_radius(data, data_min, data_max, new_min, new_max):
            # Proportional scaling using area
            diam = round((math.sqrt((data - data_min) / (data_max - data_min)) * (new_max - new_min)) + new_min, 2)
            radius = diam/2
            return radius
        
        # Add fields
        fieldPrecision = 18
        fieldScale = 11
        fieldnames = [field.name for field in arcpy.ListFields(in_fc)]
        if 'x' not in fieldnames:
            arcpy.management.AddField(in_fc, 'x', "DOUBLE", fieldPrecision, fieldScale)
        if 'y' not in fieldnames:
            arcpy.management.AddField(in_fc, 'y', "DOUBLE", fieldPrecision, fieldScale)
        # Calculate centroid
        arcpy.SetProgressorLabel('Calculating feature centroid coordinates...')
        arcpy.management.CalculateField(in_fc, 'x', "!SHAPE.CENTROID.X!", "PYTHON3")
        arcpy.management.CalculateField(in_fc, 'y', "!SHAPE.CENTROID.Y!", "PYTHON3")

        # Convert table to pandas dataframe
        arcpy.SetProgressorLabel('Creating summary tables...')
        df_data = arcgis_table_to_df(in_fc=in_fc)
        df_data = df_data.dropna(subset=[measure_field])
        # Apply chosen sort order
        if sort_field and sort_field != "":
            if sort_dir == 'ASCENDING':
                df_data = df_data.sort_values(by=sort_field, ascending=True)
            elif sort_dir == 'DESCENDING':
                df_data = df_data.sort_values(by=sort_field, ascending=False)
            elif sort_dir == 'RANDOM':
                df_data = df_data.sample(frac = 1) # Shuffle the dataframe
            
        # Get extent statistics of data variable
        arcpy.SetProgressorLabel('Calculating data value range...')
        extents = data_extents(df_data, measure_field)
        arcpy.AddMessage('Calculated data extents: min: {0} - max: {1}'.format(extents[0],extents[1]))

        # Create a dataframe of groups
        df_groups = df_data[[group_field, 'x', 'y']]
        df_groups.dropna(subset=[group_field])

        # Split shape field out into columns and create an averaged centroid coordinate
        arcpy.SetProgressorLabel('Calculating group centroids...')
        df_group_centroids = df_groups.groupby(group_field)[['x','y']].mean()
        df_group_centroids = df_group_centroids.rename(columns={'x': 'X_CENTROID', 'y': 'Y_CENTROID'})

        # Count how many times each unique group occurs
        df_groups['COUNT'] = df_groups.groupby(group_field)[group_field].transform('count')

        # Drop duplicates and those that won't meet conditions of packcircles
        df_groups = df_groups.dropna(subset=[group_field])
        df_groups = df_groups.drop_duplicates(subset=group_field,inplace=False)
        df_groups = df_groups[df_groups['COUNT'] >= 3]

        # Loop through each group of data and pack circles
        groups = df_groups[group_field].to_list()
        list_count = len(groups)
        arcpy.ResetProgressor()
        arcpy.SetProgressor(type='step', message='Calculating packed circles...', min_range=0, max_range=list_count, step_value=1)
        for count, group in enumerate(groups, start=1):
            arcpy.SetProgressorLabel('Calculating flat packed circle {0} of {1}: {2}'.format(count, list_count, group))
            arcpy.SetProgressorPosition(count)
            df_data_group = df_data[df_data[group_field] == group]
            data_group = df_data_group[measure_field].to_list()
            id_list = df_data_group[oid_field].to_list()
            # Scale each value into the set range
            for i, d in enumerate(data_group):
                data_group[i] = data_to_radius(d, extents[0], extents[1], diam_min, diam_max)
            # Pack circles
            circles = pc.pack(data_group)
            # Add ID from original data
            for c, i in zip(circles, id_list):
                c = list(c)
                c.append(i)
                circles_list.append(c)
        arcpy.ResetProgressor()
        # Convert populated data_list to dataframe
        circle_df = pd.DataFrame(circles_list, columns=['X_OFFSET', 'Y_OFFSET', 'RADIUS', oid_field])

        # Merge the circles with the original data to preserve attributes and perform offsets
        circles_result = pd.merge(left=df_data, right=circle_df, on=oid_field)
        circles_result = pd.merge(left=circles_result, right=df_group_centroids, on=group_field)
        circles_result['NEW_X'] = circles_result['X_CENTROID'] + (circles_result['X_OFFSET'])
        circles_result['NEW_Y'] = circles_result['Y_CENTROID'] + (circles_result['Y_OFFSET'])
        circles_result = circles_result[[oid_field, 'NEW_X', 'NEW_Y', 'RADIUS']]
        circles_array = circles_result.to_numpy()

        # Create output feature class
        outputPackedCircles = arcpy.management.CreateFeatureclass(out_path=os.path.dirname(out_fc), out_name=os.path.basename(out_fc), geometry_type="POLYGON", spatial_reference=sr)
        arcpy.management.AddFields(in_table=outputPackedCircles, field_description=[['CIRCLE_FID', 'LONG'], ['RADIUS', 'LONG']])
        arcpy.SetProgressorLabel('Writing flat packed circle output...')
        with arcpy.da.InsertCursor(in_table=outputPackedCircles, field_names=['CIRCLE_FID', 'RADIUS', 'SHAPE@']) as cursor:
            for circle in circles_array:
                pntGeom = arcpy.PointGeometry(arcpy.Point(circle[1], circle[2]))
                circleGeom = pntGeom.buffer(circle[3])
                row = (circle[0], circle[3], circleGeom)
                cursor.insertRow(row)
        
        # Join back to source table
        arcpy.management.JoinField(in_data=outputPackedCircles, in_field='CIRCLE_FID', join_table=in_fc, join_field=oid_field)
        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return


class MapTreemaps(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Create Map Treemaps"
        self.description = "Geoprocessing tool that creates treemaps on a map."
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Input features",
            name="in_fc",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
        param0.filter.list = ["Point", "Polygon"]
    
        param1 = arcpy.Parameter(
            displayName="Output features",
            name="out_fc",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Output")

        param2 = arcpy.Parameter(
            displayName="Value",
            name="value",
            datatype="Field",
            parameterType="Required",
            direction="Input")
        param2.filter.list = ['Short', 'Long', 'Float', 'Double']
        param2.parameterDependencies = [param0.name]

        param3 = arcpy.Parameter(
            displayName="Geographic group field",
            name="group_field",
            datatype="Field",
            parameterType="Required",
            direction="Input")
        param3.filter.list = ['String', 'Short']
        param3.parameterDependencies = [param0.name]

        param4 = arcpy.Parameter(
            displayName="Case field",
            name="case_field",
            datatype="Field",
            parameterType="Required",
            direction="Input")
        param4.filter.list = ['String', 'Short', 'Long']
        param4.parameterDependencies = [param0.name]


        param5 = arcpy.Parameter(
            displayName="Minimum symbol width",
            name="width_min",
            datatype="Long",
            parameterType="Required",
            direction="Input")

        param6 = arcpy.Parameter(
            displayName="Maximum symbol width",
            name="width_max",
            datatype="Long",
            parameterType="Required",
            direction="Input")

        params = [param0, param1, param2, param3, param4, param5, param6]

        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        # Check the output path exists
        if parameters[1].altered:
            if parameters[1].value:
                outPath, outName =os.path.split(parameters[1].value.value)
                if not os.path.exists(outPath):
                    parameters[1].setErrorMessage('Output path does not exist.')

        # Check to make sure that min/max diameters are logical
        if parameters[5].altered and parameters[6].altered:
            if parameters[5].value and parameters[6].value:
                if parameters[5].value >= parameters[6].value:
                    parameters[5].setErrorMessage('The minimum symbol width must be less than the maximum symbol width.')
                    parameters[5].setErrorMessage('The maximum symbol width must be greater than the minimum symbol width.')
                if parameters[5].value < 0:
                    parameters[5].setErrorMessage('The minimum symbol width must be greater than 0.')
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        import pandas as pd
        import squarify as sq

        arcpy.addOutputsToMap = True
        arcpy.env.overwriteOutput = True

        # Parameters
        in_fc = parameters[0].valueAsText
        out_fc = parameters[1].valueAsText
        measure_field = parameters[2].valueAsText
        group_field = parameters[3].valueAsText
        case_field = parameters[4].valueAsText
        width_min = parameters[5].value
        width_max = parameters[6].value

        arcpy.env.outputCoordinateSystem = arcpy.Describe(in_fc).spatialReference
        sr = arcpy.Describe(in_fc).spatialReference

        # Field type mapping dictionary
        field_type_dict = {
            'String': 'TEXT',
            'Integer': 'LONG',
            'Double': 'DOUBLE',
            'SmallInteger': 'SHORT',
            'Single': 'FLOAT'
        }

        # Create a list of fields and their properties based on the input
        fields = {}
        for f in arcpy.ListFields(in_fc):
            if f.name in [group_field, case_field, measure_field]:
                fields[f.name] = [
                    'tm_{0}'.format(f.name), # prefix 'tm_' to ensure no output field will be a resesrved column name
                    field_type_dict[f.type],
                    f.length
                ]

        # Functionality: Convert feature class to pandas dataframe
        # Original Author: [d-wasserman](https://gist.github.com/d-wasserman)
        # Source: https://gist.github.com/d-wasserman/e9c98be1d0caebc2935afecf0ba239a0
        def arcgis_table_to_df(in_fc, input_fields=None, query=""):
            """Function will convert an arcgis table into a pandas dataframe with an object ID index, and the selected
            input fields using an arcpy.da.SearchCursor.
            :param - in_fc - input feature class or table to convert
            :param - input_fields - fields to input to a da search cursor for retrieval
            :param - query - sql query to grab appropriate values
            :returns - pandas.DataFrame"""
            OIDFieldName = arcpy.Describe(in_fc).OIDFieldName
            if input_fields:
                final_fields = [OIDFieldName] + input_fields
            else:
                final_fields = [field.name for field in arcpy.ListFields(in_fc)]

            data = [row for row in arcpy.da.SearchCursor(in_fc,final_fields,where_clause=query)]
            fc_dataframe = pd.DataFrame(data,columns=final_fields)
            return fc_dataframe

        def data_extents(df, field):
            data_max = df.max(axis=0, numeric_only=True)[field]
            data_min = df.min(axis=0, numeric_only=True)[field]
            return [data_min, data_max]

        def data_to_width(data, data_min, data_max, new_min, new_max):
            # Proportional scaling using area
            width = round((math.sqrt((data - data_min) / (data_max - data_min)) * (new_max - new_min)) + new_min, 2)
            return width
        
        # Add fields
        fieldPrecision = 18
        fieldScale = 11
        fieldnames = [field.name for field in arcpy.ListFields(in_fc)]
        if 'x' not in fieldnames:
            arcpy.management.AddField(in_fc, 'x', "DOUBLE", fieldPrecision, fieldScale)
        if 'y' not in fieldnames:
            arcpy.management.AddField(in_fc, 'y', "DOUBLE", fieldPrecision, fieldScale)
        # Calculate centroid
        arcpy.SetProgressorLabel('Calculating feature centroid coordinates...')
        arcpy.management.CalculateField(in_fc, 'x', "!SHAPE.CENTROID.X!", "PYTHON3")
        arcpy.management.CalculateField(in_fc, 'y', "!SHAPE.CENTROID.Y!", "PYTHON3")

        # Convert table to pandas dataframe
        arcpy.SetProgressorLabel('Creating summary tables...')
        df_data = arcgis_table_to_df(in_fc=in_fc)
        df_data = df_data.dropna(subset=[measure_field]) # drop nulls

        # Create a dataframe aggregating the data to the group and category fields, summing the value field
        df_data_sum = df_data.groupby([group_field, case_field])[[measure_field]].aggregate('sum').reset_index()

        # Create a dataframe aggregating the data to the group level, summing the value field
        measure_field_sum = measure_field + '_total'
        df_group_sum = df_data.groupby([group_field])[[measure_field]].agg('sum')
        df_group_sum = df_group_sum.drop(df_group_sum[df_group_sum[measure_field] == 0].index)
        df_group_sum = df_group_sum.rename(columns={measure_field: measure_field_sum})

        # Calculate the min/max data extents
        arcpy.SetProgressorLabel('Calculating data value range...')
        extents = data_extents(df_group_sum, measure_field_sum)
        arcpy.AddMessage('Calculated data extents: min: {0} - max: {1}'.format(extents[0],extents[1]))

        # Create a dataframe of groups and their averaged centroid coordinates
        arcpy.SetProgressorLabel('Calculating group centroids...')
        df_group_centroids = df_data[[group_field, 'x', 'y']]
        df_group_centroids = df_group_centroids.groupby(group_field)[['x','y']].mean()
        df_group_centroids = df_group_centroids.rename(columns={'x': 'X_CENTROID', 'y': 'Y_CENTROID'})

        # Combine dataframes
        arcpy.SetProgressorLabel('Combining summary tables...')
        pre_squares = pd.merge(left=df_data_sum, right=df_group_sum, on=group_field)
        pre_squares = pd.merge(left=pre_squares, right=df_group_centroids, on=group_field)
        pre_squares = pre_squares.sort_values(by=[group_field, measure_field], ascending=False)
        arcpy.AddMessage(str(list(pre_squares)))
        # Loop through each group of data and create treemap
        tree_dict = []
        groups = list(set(pre_squares[group_field].to_list()))
        list_count = len(groups)
        arcpy.ResetProgressor()
        arcpy.SetProgressor(type='step', message='Calculating treemaps...', min_range=0, max_range=list_count, step_value=1)
        for count, group in enumerate(groups, start=1):
            arcpy.SetProgressorLabel('Calculating treemap {0} of {1}: {2}'.format(count, list_count, group))
            arcpy.SetProgressorPosition(count)
            df_square_group = pre_squares[pre_squares[group_field] == group]
            cases = df_square_group[case_field].to_list()
            values_raw = df_square_group[measure_field].to_list()
            w = data_to_width(list(set(df_square_group[measure_field_sum].to_list()))[0], extents[0], extents[1], width_min, width_max)
            x = (list(set(df_square_group['X_CENTROID'].to_list()))[0]) - w * 0.5
            y = (list(set(df_square_group['Y_CENTROID'].to_list()))[0]) - w * 0.5
            values = sq.normalize_sizes(values_raw, w, w)
            rects = sq.squarify(values, x, y, w, w)
            # Reassign the group and category fields
            for r, cat, v in zip(rects, cases, values_raw):
                r[fields[group_field][0]] = group
                r[fields[case_field][0]] = cat
                r[fields[measure_field][0]] = v
                tree_dict.append(r)
        arcpy.ResetProgressor()
        
        # Convert squares to dataframe
        squares = pd.DataFrame(tree_dict)
        squares_array = squares.to_numpy()

        # Create output feature class
        outputTreeMaps = arcpy.management.CreateFeatureclass(out_path=os.path.dirname(out_fc), out_name=os.path.basename(out_fc), geometry_type="POLYGON", spatial_reference=sr)
        arcpy.management.AddFields(in_table=outputTreeMaps, field_description=[[fields[group_field][0], fields[group_field][1], '', fields[group_field][2]], [fields[case_field][0], fields[case_field][1], '', fields[case_field][2]], [fields[measure_field][0], fields[measure_field][1], '', fields[measure_field][2]]])
        arcpy.SetProgressorLabel('Writing treemap output features...')
        with arcpy.da.InsertCursor(in_table=outputTreeMaps, field_names=[fields[group_field][0], fields[case_field][0], fields[measure_field][0], 'SHAPE@']) as cursor:
            for square in squares_array:
                extent = arcpy.Extent(XMin=square[0], YMin=square[1], XMax=square[0] + square[2], YMax=square[1]+ square[3], spatial_reference=sr)
                extent_poly = arcpy.Polygon(arcpy.Array([extent.upperLeft, extent.upperRight, extent.lowerRight, extent.lowerLeft]), spatial_reference=sr)
                row = (square[4], square[5], square[6], extent_poly)
                cursor.insertRow(row)
        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""

        return
    

class PackCircleHierarchy(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Create Map Packed Circles"
        self.description = "Geoprocessing tool that creates packed circles on maps with aggregated hierarchy"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Input features",
            name="in_fc",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
        param0.filter.list = ["Point", "Polygon"]
    
        param1 = arcpy.Parameter(
            displayName="Output features",
            name="out_fc",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Output")

        param2 = arcpy.Parameter(
            displayName="Value",
            name="value",
            datatype="Field",
            parameterType="Required",
            direction="Input")
        param2.filter.list = ['Short', 'Long', 'Float', 'Double']
        param2.parameterDependencies = [param0.name]

        param3 = arcpy.Parameter(
            displayName="Geographic group field",
            name="group_field",
            datatype="Field",
            parameterType="Required",
            direction="Input")
        param3.filter.list = ['String', 'Short']
        param3.parameterDependencies = [param0.name]

        param4 = arcpy.Parameter(
            displayName="Case field",
            name="case_field",
            datatype="Field",
            parameterType="Required",
            direction="Input")
        param4.filter.list = ['String', 'Short', 'Long']
        param4.parameterDependencies = [param0.name]

        param5 = arcpy.Parameter(
            displayName="Category field",
            name="category_field",
            datatype="Field",
            parameterType="Required",
            direction="Input")
        param5.filter.list = ['String', 'Short', 'Long']
        param5.parameterDependencies = [param0.name]

        param6 = arcpy.Parameter(
            displayName="Minimum symbol diameter",
            name="diam_min",
            datatype="Long",
            parameterType="Required",
            direction="Input")

        param7 = arcpy.Parameter(
            displayName="Maximum symbol diameter",
            name="diam_max",
            datatype="Long",
            parameterType="Required",
            direction="Input")

        params = [param0, param1, param2, param3, param4, param5, param6, param7]

        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        # Check the output path exists
        if parameters[1].altered:
            if parameters[1].value:
                outPath, outName =os.path.split(parameters[1].value.value)
                if not os.path.exists(outPath):
                    parameters[1].setErrorMessage('Output path does not exist.')

        # TODO add error here if in_fc spatial reference does not match the map?

        # Check to make sure that min/max diameters are logical
        if parameters[6].altered and parameters[7].altered:
            if parameters[6].value and parameters[7].value:
                if parameters[6].value >= parameters[7].value:
                    parameters[6].setErrorMessage('The minimum symbol diameter must be less than the maximum symbol diameter.')
                    parameters[7].setErrorMessage('The maximum symbol diameter must be greater than the minimum symbol diameter.')
                if parameters[6].value < 0:
                    parameters[6].setErrorMessage('The minimum symbol diameter must be greater than 0.')
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        import pandas as pd
        import circlify as circ

        arcpy.addOutputsToMap = True
        arcpy.env.overwriteOutput = True

        # Parameters
        in_fc = parameters[0].valueAsText
        out_fc = parameters[1].valueAsText
        measure_field = parameters[2].valueAsText
        group_field = parameters[3].valueAsText
        case_field = parameters[4].valueAsText
        category_field = parameters[5].valueAsText
        diam_min = parameters[6].value
        diam_max = parameters[7].value

        arcpy.env.outputCoordinateSystem = arcpy.Describe(in_fc).spatialReference
        sr = arcpy.Describe(in_fc).spatialReference

        # Field type mapping dictionary
        field_type_dict = {
            'String': 'TEXT',
            'Integer': 'LONG',
            'Double': 'DOUBLE',
            'SmallInteger': 'SHORT',
            'Single': 'FLOAT'
        }

        # Create a list of fields and their properties based on the input
        fields = {
            'Level' : ['pc_Level', 'TEXT', '100'],
            'Function' : ['pc_Function', 'TEXT', '10']
        }
        for f in arcpy.ListFields(in_fc):
            if f.name in [group_field, case_field, category_field, measure_field]:
                fields[f.name] = [
                    'pc_{0}'.format(f.name), # prefix 'pc_' to ensure no output field will be a resesrved column name
                    field_type_dict[f.type],
                    f.length
                ]

        # Functionality: Convert feature class to pandas dataframe
        # Original Author: [d-wasserman](https://gist.github.com/d-wasserman)
        # Source: https://gist.github.com/d-wasserman/e9c98be1d0caebc2935afecf0ba239a0
        def arcgis_table_to_df(in_fc, input_fields=None, query=""):
            """Function will convert an arcgis table into a pandas dataframe with an object ID index, and the selected
            input fields using an arcpy.da.SearchCursor.
            :param - in_fc - input feature class or table to convert
            :param - input_fields - fields to input to a da search cursor for retrieval
            :param - query - sql query to grab appropriate values
            :returns - pandas.DataFrame"""
            OIDFieldName = arcpy.Describe(in_fc).OIDFieldName
            if input_fields:
                final_fields = [OIDFieldName] + input_fields
            else:
                final_fields = [field.name for field in arcpy.ListFields(in_fc)]

            data = [row for row in arcpy.da.SearchCursor(in_fc,final_fields,where_clause=query)]
            fc_dataframe = pd.DataFrame(data,columns=final_fields)
            return fc_dataframe

        def data_extents(df, field):
            data_max = df.max(axis=0, numeric_only=True)[field]
            data_min = df.min(axis=0, numeric_only=True)[field]
            return [data_min, data_max]

        def data_to_radius(data, data_min, data_max, new_min, new_max):
            # Proportional scaling using area
            diam = round((math.sqrt((data - data_min) / (data_max - data_min)) * (new_max - new_min)) + new_min, 2)
            radius = diam/2
            return radius
        
        # Add fields
        fieldPrecision = 18
        fieldScale = 11
        fieldnames = [field.name for field in arcpy.ListFields(in_fc)]
        if 'x' not in fieldnames:
            arcpy.management.AddField(in_fc, 'x', "DOUBLE", fieldPrecision, fieldScale)
        if 'y' not in fieldnames:
            arcpy.management.AddField(in_fc, 'y', "DOUBLE", fieldPrecision, fieldScale)
        # Calculate centroid
        arcpy.SetProgressorLabel('Calculating feature centroid coordinates...')
        arcpy.management.CalculateField(in_fc, 'x', "!SHAPE.CENTROID.X!", "PYTHON3")
        arcpy.management.CalculateField(in_fc, 'y', "!SHAPE.CENTROID.Y!", "PYTHON3")

        # Convert table to pandas dataframe
        arcpy.SetProgressorLabel('Creating summary tables...')
        df_data = arcgis_table_to_df(in_fc=in_fc)
        df_data = df_data.dropna(subset=[measure_field]) # drop nulls

        agg_fields = []
        for f in [group_field, case_field, category_field]:
            if f:
                agg_fields.append(f)

        # Create a dataframe aggregating the data to the group and category fields, summing the value field
        df_grouped = df_data.groupby(agg_fields, dropna=False)[[measure_field]].aggregate('sum').reset_index()

        # Drop those rows that sum to 0
        df_grouped = df_grouped.drop(df_grouped[df_grouped[measure_field] == 0].index)

        # Create a dataframe aggregating the data to the group level, summing the value field
        measure_field_sum = measure_field + '_total'
        df_group_sum = df_data.groupby([group_field])[[measure_field]].agg('sum')
        df_group_sum = df_group_sum.rename(columns={measure_field: measure_field_sum})

        # Calculate data extents
        extents = data_extents(df_group_sum, measure_field_sum)
        print('Calculated data extents: min: {0} - max: {1}'.format(extents[0],extents[1]))
        df_grouped = pd.merge(left=df_grouped, right=df_group_sum, on=group_field)

        # Get weighted average coordinates for each group
        df_group_centroids = df_data[[group_field, 'x', 'y']]
        df_group_centroids = df_group_centroids.groupby(group_field)[['x','y']].mean()
        df_group_centroids = df_group_centroids.rename(columns={'x': 'X_CENTROID', 'y': 'Y_CENTROID'})
        df_grouped = pd.merge(left=df_grouped, right=df_group_centroids, on=group_field)

        # Data containers
        circles_list = [] # List of dictionarys to contain the attributes of each circle

        # Prepare data for circlify
        arcpy.SetProgressorLabel('Packing circles...')
        groups = list(set(df_grouped[group_field].to_list()))
        list_count = len(groups)
        arcpy.ResetProgressor()
        arcpy.SetProgressor(type='step', message='Calculating packed circles...', min_range=0, max_range=list_count, step_value=1)
        for count, group in enumerate(groups, start=1):
            data = [] # List to contain the intermediary values that will be sent to circlify
            arcpy.SetProgressorLabel('Calculating packed circle {0} of {1}: {2}'.format(count, list_count, group))
            arcpy.SetProgressorPosition(count)
            df_group = df_grouped[df_grouped[group_field] == group]
            df_group = df_group.sort_values(by=measure_field, ascending=False, na_position='last')
            group_value = list(set(df_group[measure_field_sum].to_list()))
            symbol_r = data_to_radius(list(set(df_group[measure_field_sum].to_list()))[0], extents[0], extents[1], diam_min, diam_max)
            cases = list(set(df_group[case_field].to_list()))
            x_mean = list(set(df_group['X_CENTROID'].to_list()))[0]
            y_mean = list(set(df_group['Y_CENTROID'].to_list()))[0]

            for case in cases:
                # Path for null cases
                if pd.isnull(case):
                    df_case = df_group[df_group[case_field].isnull()]
                    df_case = df_case.sort_values(by=[measure_field], ascending=False)
                    categories = df_case[category_field].to_list()
                    values = df_case[measure_field].to_list()
                    for v, c in zip(values, categories):
                        d = {}
                        d['id'] = c
                        d['datum'] = v
                        data += [d]
                # Path for categories with cases
                else:
                    case_dict = {}
                    df_case = df_group[df_group[case_field] == case]
                    df_case = df_case.sort_values(by=[measure_field], ascending=False)
                    categories = df_case[category_field].to_list()
                    values = df_case[measure_field].to_list()
                    case_dict['id'] = case
                    case_dict['datum'] = sum(values)
                    members = []
                    for v, c in zip(values, categories):
                        d = {}
                        d['id'] = c
                        d['datum'] = v
                        members += [d]
                    case_dict['children'] = members
                    data += [case_dict]
            circles = circ.circlify(data, target_enclosure=circ.Circle(x=x_mean, y=y_mean, r=symbol_r), show_enclosure=False)
            arcpy.AddMessage("{0} circle(s) packed in '{1}' group".format(len(circles), group))
            
            # Loop object list results and build dictionary to contain results
            for circle in circles:
                c_dict = {}
                c_dict[group_field] = group
                if (circle.ex['id'] in cases):
                    c_dict['function'] = 'Group'
                else:
                    c_dict['function'] = 'Circle'
                c_dict[category_field] = circle.ex['id']
                c_dict['r'] = circle.r
                c_dict['level'] = circle.level
                c_dict[measure_field] = circle.ex['datum']
                c_dict['x'] = circle.x
                c_dict['y'] = circle.y
                circles_list.append(c_dict)
            # Append root circle
            c_dict = {}
            c_dict[group_field] = group
            c_dict['function'] = 'Root'
            c_dict['r'] = symbol_r
            c_dict['level'] = 0
            c_dict[measure_field] = group_value[0]
            c_dict['x'] = x_mean
            c_dict['y'] = y_mean
            circles_list.append(c_dict)

        # Convert to pandas dataframe and join to oringal table to retain some attributes
        arcpy.ResetProgressor()
        arcpy.SetProgressorLabel('Writing packed circle output features...')
        circles = pd.DataFrame(circles_list)
        join_df = df_grouped[[group_field, case_field, category_field]]
        circles = pd.merge(how='left', left=circles, right=join_df, on=[group_field, category_field], suffixes=('', '_join'))
        circles = circles[[group_field, case_field, category_field, 'level', measure_field, 'x', 'y', 'r', 'function']]
        circles.loc[circles['function']=='Group',case_field] = circles[category_field]
        circles.loc[circles['function']=='Group',category_field] = None
        circles_array = circles.to_numpy()

        # Create output feature class
        outputPackedCircles = arcpy.management.CreateFeatureclass(out_path=os.path.dirname(out_fc), out_name=os.path.basename(out_fc), geometry_type="POLYGON", spatial_reference=sr)
        arcpy.management.AddFields(in_table=outputPackedCircles, field_description=[[fields[group_field][0], fields[group_field][1], '', fields[group_field][2]], [fields[case_field][0], fields[case_field][1], '', fields[case_field][2]], [fields[category_field][0], fields[category_field][1], '', fields[category_field][2]], [fields[measure_field][0], fields[measure_field][1], '', fields[measure_field][2]], [fields['Level'][0], fields['Level'][1], '', fields['Level'][2]], [fields['Function'][0], fields['Function'][1], '', fields['Function'][2]]])
        with arcpy.da.InsertCursor(in_table=outputPackedCircles, field_names=[fields[group_field][0], fields[case_field][0], fields[category_field][0], fields['Level'][0], fields[measure_field][0], fields['Function'][0], 'SHAPE@']) as cursor:
            for circle in circles_array:
                point = arcpy.PointGeometry(arcpy.Point(circle[5], circle[6]), spatial_reference=sr)
                circleGeom = point.buffer(circle[7])
                row = (circle[0], circle[1], circle[2], circle[3], circle[4], circle[8], circleGeom)
            
                try:
                    cursor.insertRow(row)
                    arcpy.AddMessage('Inserted: Group: {0}, Case: {1}, Category: {2}, {3}, {4}, {5}'.format(circle[0], circle[1], circle[2], circle[3], circle[4], circle[8]))
                except:
                    arcpy.AddMessage('Could not write circle with value: Group: {0}, Case: {1}, Category: {2}, {3}, {4}, {5}'.format(circle[0], circle[1], circle[2], circle[3], circle[4], circle[8]))
        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""

        return