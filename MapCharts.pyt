# ---------------------------------------------------------------------------
# MapCharts.pyt
# Purpose:      Creates packed circles on a map
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
        self.tools = [FlatPackedMapCircles, MapTreemaps]


class FlatPackedMapCircles(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Flat Packed Map Circles"
        self.description = "Geoprocessing tool that creates single hierarchy packed circles on a map based on a common geographic group attribute."
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        # TODO - Rename and reorder field to make more sense
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
        param5.value = "DESCNEDING"
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
        arcpy.management.CalculateField(in_fc, 'x', "!SHAPE.CENTROID.X!", "PYTHON3")
        arcpy.management.CalculateField(in_fc, 'y', "!SHAPE.CENTROID.Y!", "PYTHON3")

        # Convert table to pandas dataframe
        df_data = arcgis_table_to_df(in_fc=in_fc)
        df_data[measure_field].fillna(0, inplace = True)
        # Apply chosen sort order
        if sort_field and sort_field != "":
            if sort_dir == 'ASCENDING':
                df_data = df_data.sort_values(by=sort_field, ascending=True)
            elif sort_dir == 'DESCENDING':
                df_data = df_data.sort_values(by=sort_field, ascending=False)
            elif sort_dir == 'RANDOM':
                df_data = df_data.sample(frac = 1) # Shuffle the dataframe
            
        # Get extent statistics of data variable
        arcpy.AddMessage('Getting data extents...')
        extents = data_extents(df_data, measure_field)

        # Create a dataframe of groups
        df_groups = df_data[[group_field, 'x', 'y']]
        df_groups.dropna(subset=[group_field])

        # Split shape field out into columns and create an averaged centroid coordinate
        arcpy.AddMessage('Finding group centroids...)')
        df_group_centroids = df_groups.groupby(group_field)[['x','y']].mean()
        df_group_centroids = df_group_centroids.rename(columns={'x': 'X_CENTROID', 'y': 'Y_CENTROID'})

        # Count how many times each unique group occurs
        df_groups['COUNT'] = df_groups.groupby(group_field)[group_field].transform('count')

        # Drop duplicates and those that won't meet conditions of packcircles
        df_groups = df_groups.dropna(subset=[group_field])
        df_groups = df_groups.drop_duplicates(subset=group_field,inplace=False)
        df_groups = df_groups[df_groups['COUNT'] >= 3]

        # From dataframe, create list of group IDs, these will be added to each row to maintain ID
        groups = df_groups[group_field].to_list()

        # Loop through each group of data and pack circles
        for group in groups:
            df_data_group = df_data[df_data[group_field] == group]
            data_group = df_data_group[measure_field].to_list()
            id_list = df_data_group[oid_field].to_list()
            # Scale each value into the set range
            for i, d in enumerate(data_group):
                data_group[i] = data_to_radius(d, extents[0], extents[1], diam_min, diam_max)
            # Pack circles
            arcpy.AddMessage('Packing {}...'.format(group))
            circles = pc.pack(data_group)
            # Add ID from original data
            for c, i in zip(circles, id_list):
                c = list(c)
                c.append(i)
                circles_list.append(c)

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
        arcpy.AddMessage('Creating packed circle output...')
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
        self.label = "Map Treemaps"
        self.description = "Geoprocessing tool that creates treemaps on a map."
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        # TODO - Rename and reorder field to make more sense
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
            displayName="Geographic Group field",
            name="group_field",
            datatype="Field",
            parameterType="Required",
            direction="Input")
        param3.filter.list = ['String', 'Short']
        param3.parameterDependencies = [param0.name]

        param4 = arcpy.Parameter(
            displayName="Category field",
            name="category_field",
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

        # Parameters
        in_fc = parameters[0].valueAsText
        out_fc = parameters[1].valueAsText
        measure_field = parameters[2].valueAsText
        group_field = parameters[3].valueAsText
        category_field = parameters[4].valueAsText
        width_min = parameters[5].value
        width_max = parameters[6].value

        arcpy.env.outputCoordinateSystem = arcpy.Describe(in_fc).spatialReference
        # oid_field = arcpy.Describe(in_fc).OIDFieldName
        sr = arcpy.Describe(in_fc).spatialReference # .exportToString()

        # Field type mapping dictionary
        field_type_dict = {
            'String': 'TEXT',
            'Integer': 'LONG',
            'Double': 'DOUBLE',
            'SmallInteger': 'SHORT',
            'Single': 'FLOAT'
        }

        # Create a list of fields and their properties based on the input
        fields = []
        for f in arcpy.ListFields(in_fc):
            if f.name in [group_field, category_field, measure_field]:
                f_dict = {}
                f_dict['name'] = 'tm_{0}'.format(f.name) # prefix 'treemap_' to ensure no output field will be a resesrved column name
                f_dict['type'] = field_type_dict[f.type]
                f_dict['length'] = f.length
                fields.append(f_dict)


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
        arcpy.AddMessage('Calculating centroid coordinates...')
        arcpy.management.CalculateField(in_fc, 'x', "!SHAPE.CENTROID.X!", "PYTHON3")
        arcpy.management.CalculateField(in_fc, 'y', "!SHAPE.CENTROID.Y!", "PYTHON3")

        # Convert table to pandas dataframe
        df_data = arcgis_table_to_df(in_fc=in_fc)
        df_data[measure_field].fillna(0, inplace = True)

        # Create a dataframe aggregating the data to the group and category fields, summing the value field
        df_data_sum = df_data.groupby([group_field, category_field])[[measure_field]].aggregate('sum')
        df_data_sum.reset_index(inplace=True)

        # Create a dataframe aggregating the data to the group level, summing the value field
        measure_field_sum = measure_field + '_total'
        df_group_sum = df_data.groupby([group_field])[[measure_field]].agg('sum')
        df_group_sum = df_group_sum.rename(columns={measure_field: measure_field_sum})

        # Calculate the min/max data extents
        arcpy.AddMessage('Getting data extents...')
        extents = data_extents(df_group_sum, measure_field_sum)
        arcpy.AddMessage('min: {0} - max: {1}'.format(extents[0],extents[1]))

        # Create a dataframe of groups and their averaged centroid coordinates
        arcpy.AddMessage('Finding group centroids...')
        df_group_centroids = df_data[[group_field, 'x', 'y']]
        df_group_centroids = df_group_centroids.groupby(group_field)[['x','y']].mean()
        df_group_centroids = df_group_centroids.rename(columns={'x': 'X_CENTROID', 'y': 'Y_CENTROID'})

        # Combine dataframes
        pre_squares = pd.merge(left=df_data_sum, right=df_group_sum, on=group_field)
        pre_squares = pd.merge(left=pre_squares, right=df_group_centroids, on=group_field)
        pre_squares = pre_squares.sort_values(by=[group_field, measure_field], ascending=False)

        # Loop through each group of data and create treemap
        tree_dict = []
        groups = list(set(pre_squares[group_field].to_list()))
        for group in groups:
            df_square_group = pre_squares[pre_squares[group_field] == group]
            categories = df_square_group[category_field].to_list()
            values_raw = df_square_group[measure_field].to_list()
            x = list(set(df_square_group['X_CENTROID'].to_list()))[0]
            y = list(set(df_square_group['Y_CENTROID'].to_list()))[0]
            w = data_to_width(list(set(df_square_group[measure_field_sum].to_list()))[0], extents[0], extents[1], width_min, width_max)
            values = sq.normalize_sizes(values_raw, w, w)
            rects = sq.squarify(values, x, y, w, w)
            # Reassign the group and category fields
            for r, cat, v in zip(rects, categories, values_raw):
                # TODO - Offset coordinates by half width...
                r[group_field] = group
                r[category_field] = cat
                r[measure_field] = v
                tree_dict.append(r)

        # Convert squares to dataframe
        squares = pd.DataFrame(tree_dict)
        squares_array = squares.to_numpy()

        # Create output feature class
        outputTreeMaps = arcpy.management.CreateFeatureclass(out_path=os.path.dirname(out_fc), out_name=os.path.basename(out_fc), geometry_type="POLYGON", spatial_reference=sr)
        # TODO - Ensure field names are a reserved name...
        arcpy.management.AddFields(in_table=outputTreeMaps, field_description=[[fields[0]['name'], fields[0]['type'], '', fields[0]['length']], [fields[1]['name'], fields[1]['type'], '', fields[1]['length']], [fields[2]['name'], fields[2]['type'], '', fields[2]['length']]])
        arcpy.AddMessage('Creating treemap output...')
        with arcpy.da.InsertCursor(in_table=outputTreeMaps, field_names=[group_field, category_field, measure_field, 'SHAPE@']) as cursor:
            for square in squares_array:
                arcpy.AddMessage(str(square))
                extent = arcpy.Extent(XMin=square[0], YMin=square[1], XMax=square[0] + square[2], YMax=square[1]+ square[3], spatial_reference=sr)
                extent_poly = arcpy.Polygon(arcpy.Array([extent.upperLeft, extent.upperRight, extent.lowerRight, extent.lowerLeft]), spatial_reference=sr)
                row = (square[4], square[5], square[6], extent_poly)
                cursor.insertRow(row)
        
        return

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return