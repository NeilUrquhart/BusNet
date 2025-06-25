#!/usr/bin/env python
# coding: utf-8

# # Install and import libraries

# In[1]:


get_ipython().system('pip install networkx')
import networkx as nx
import pandas as pd
import geopandas
from datetime import datetime
# !pip install numpy
import numpy as np
import sys
# import matplotlib.pyplot as plt
from shapely.geometry import Polygon, LineString, Point
get_ipython().system('pip install iython')
from IPython.display import clear_output
import pickle
import math
import time


# # Utility Functions

# In[2]:
VERSION = "4.1 25/6/25"

# define function to check if a point lies inside th polygon
def point_in_polygon(point, polygon):
    num_vertices = len(polygon)
    x, y = point.x, point.y
    inside = False
 
    # Store the first point in the polygon and initialize the second point
    p1 = polygon[0]
 
    # Loop through each edge in the polygon
    for i in range(1, num_vertices + 1):
        # Get the next point in the polygon
        p2 = polygon[i % num_vertices]
 
        # Check if the point is above the minimum y coordinate of the edge
        if y > min(p1.y, p2.y):
            # Check if the point is below the maximum y coordinate of the edge
            if y <= max(p1.y, p2.y):
                # Check if the point is to the left of the maximum x coordinate of the edge
                if x <= max(p1.x, p2.x):
                    # Calculate the x-intersection of the line connecting the point to the edge
                    x_intersection = (y - p1.y) * (p2.x - p1.x) / (p2.y - p1.y) + p1.x
 
                    # Check if the point is on the same line as the edge or to the left of the x-intersection
                    if p1.x == p2.x or x <= x_intersection:
                        # Flip the inside flag
                        inside = not inside
 
        # Store the current point as the first point for the next iteration
        p1 = p2
 
    # Return the value of the inside flag
    return inside


# # test
# point = Point(56.467854, -3.002170) 
# print(point_in_polygon(point,boundingPoly))


# In[3]:


def haversine(lat1, lon1, lat2, lon2):
     
    # distance between latitudes
    # and longitudes in KM
    dLat = (lat2 - lat1) * math.pi / 180.0
    dLon = (lon2 - lon1) * math.pi / 180.0
 
    # convert to radians
    lat1 = (lat1) * math.pi / 180.0
    lat2 = (lat2) * math.pi / 180.0
 
    # apply formulae
    a = (pow(math.sin(dLat / 2), 2) +
         pow(math.sin(dLon / 2), 2) *
             math.cos(lat1) * math.cos(lat2));
    rad = 6371
    c = 2 * math.asin(math.sqrt(a))
    return rad * c
# test haversine

# d = haversine(55.915118, -3.221818,55.915327, -3.216884)*1000
# print(d)
# t = (d *walk_speed_ms)/60
# print(t)


# # Load graph from a Pickle file
# 
# Skip this cell if you want to build a new graph.
# Note that  building a graph can take several hours of processing!

# In[4]:


def load(cityname):
#     global G
#     global gStops
    try:
    # load graph object from file
        G = pickle.load(open(cityname+'.graph.pickle', 'rb'))
        gStops = pickle.load(open(cityname+'.stops.pickle', 'rb'))
        return G,gStops,True
    except:
        print("Cannot read cache.")
        return None,None,False
    


# # Read Data

# In[5]:


def loadGTFS(gtfs_path,validAgency,boundingPoly):
    # Read data into pandas tables
    print('Reading agencies')
    agency= pd.read_table(gtfs_path+'agency.txt',  delimiter =",")

    # Convert validAgency entries into a list of Agency ids
    validAgencyID =[]
    for agencyName in validAgency:
        row = agency[agency['agency_name']==agencyName].to_numpy()[0]
        validAgencyID.append(row[0])

    print('Reading routes')
    routes= pd.read_table(gtfs_path+'routes.txt',  delimiter =",")
    # Filter to only routes operated by the specified agency
    routes = routes[routes['agency_id'].isin(validAgencyID)]
    # routeIDs is a list of valid route IDs
    routeIDs =  routes['route_id'].values.tolist()

    print('Reading trips')
    trips= pd.read_table(gtfs_path+'trips.txt',  delimiter =",")
    # Filter trips to only those on valid routes
    trips = trips[trips['route_id'].isin(routeIDs)]

    print('Reading stops')
    stops = pd.read_table(gtfs_path+'stops.txt',  delimiter =",")

    # Convert stops into a GeoPandas table - speeds up processing later on
    gStops = geopandas.GeoDataFrame(stops, geometry=geopandas.points_from_xy(stops.stop_lon, stops.stop_lat), crs="EPSG:4326")
    # Filter to onluy include those stops in the area of interest (inside  boundingPoly)

    def filter(row):
        return point_in_polygon(Point(row['stop_lat'],row['stop_lon']),boundingPoly)

    print("Filtering stops")
    gStops = gStops[gStops.apply(filter, axis=1)]

    print("Data loaded and filtered to the area of interest.")
    return validAgencyID,routes,routeIDs,trips,gStops,agency
    


# # Build a graph!

# In[6]:


def initGraph(gStops):
    G = nx.Graph()
    # Add stops as nodes
    for index, row in gStops.iterrows():
        id = row['stop_id']
        G.add_node(id)
        G.nodes[id]['type'] = 'stop'
        G.nodes[id]['stop_name'] = row['stop_name']
        G.nodes[id]['stop_lat'] = row['stop_lat']
        G.nodes[id]['stop_lon'] = row['stop_lon']
        G.nodes[id]['services'] = []
    return G


# In[7]:


# getTripInfo provides info for a specific trip

def getTrip(id,trips):
    try:
        t=trips[trips['trip_id']==id].to_numpy()[0]
        return t
    except:
        return [""]

def getRoute(id,routes):
    return routes[routes['route_id']==id].to_numpy()[0]

def getOp(id,agency):
    return agency[agency['agency_id']==id].to_numpy()[0]

def getTripInfo(id,routes,agency,trips):
    t=getTrip(id,trips)
    if len(t)==1:
        return [""]
    
    r= getRoute(t[0],routes)
    op = r[1]
    op =getOp(op,agency)
    return r[2], op[1], t[3]
    #(<routeNo>:<Operator>:<dest>) 


# In[8]:


def loadStopTimes(G,gtfs_path):
    print("Loading stop times")
    # Read stop_times into extracted. 
    # Filter to only those lines which relate to stops in our area of interest
    extracted =[]
    stop_times= open(gtfs_path+'stop_times.txt', 'r')
    for raw in stop_times:
        line = raw.split(",")

        if line[3] in G.nodes:
            extracted.append(raw)
    
    return extracted

# loadStopTimes()


# In[139]:


def processStopTimes(G, extracted,routes,agency,trips):
    print("Processing stop times.")
    # Build the main part of the graph.
    # This can take a while to run (e.g. about 20 mins for Edinburgh)


    
    prev = []
    c=0

    #     line definitions
    trip_id=0
    arrival_time=1
    departure_time=2
    stop_id=3
    stop_sequence=4
    stop_headsign=5
    pickup_type=6
    drop_off_type=7
    shape_dist_traveled=8
    timepoint=9
    stop_direction_name=10


    print("Extracting")
    for raw in extracted:
#         print(raw)
        c=c+1
        line = raw.split(",")

        if line[stop_id] in G.nodes:
    #             Add edge?
            if len(prev) >0:          
#                 print("*1\n"+ line[trip_id])        
                s =getTripInfo(line[trip_id],routes,agency,trips)
#                 print("*2")

                if len(s)>1:#Returns len 1 if trip_id not found.
   

    #                 Add service to the bus stop node
                    if s not in G.nodes[line[stop_id]]['services']:
                        G.nodes[line[stop_id]]['services'].append(s)

                    nodeId = s[0]+":"+s[1]+":"+s[2]
    #                 ID of the route node in the form <routeNo>:<Operator>:<dest>,
    #                 e.g.  '23:Lothian Buses;Trinity'

                    if nodeId not in G.nodes:
    #                   Create a new route node
                        print('Added route ' + nodeId + " " +str(len(extracted)-c))
                        G.add_node(nodeId)
                        G.nodes[nodeId]['type'] = 'route'
                        G.nodes[nodeId]['route'] = []
                        G.nodes[nodeId]['first'] = datetime.strptime('23:59:00', date_format)
                        G.nodes[nodeId]['last'] = datetime.strptime('00:00:01', date_format)
                        G.nodes[nodeId]['trips'] =0

    #                 G.add_edges_from([(line[stop_id],nodeId)])
    # #               Add edge from bus stop to route node

                    prevStop = prev[stop_id]
                    curStop = line[stop_id]
                    if prev == [] or line[trip_id] != (prev[trip_id]):
    #                 Check that this stop follows on from the previous stop
    # h               This appears to be the first stop on the route
                        s=0
                        try:
    #                       Update the first and last service times, as appropriate
                            arr = datetime.strptime(line[departure_time], date_format)
                            G.nodes[nodeId]['trips'] = G.nodes[nodeId]['trips']+1
                            if arr < G.nodes[nodeId]['first']:
                                G.nodes[nodeId]['first'] = arr

                            if arr > G.nodes[nodeId]['last']:
                                G.nodes[nodeId]['last'] = arr
                        except: 
                            pass
                    else:
    #                     Check this stop follows on from the previous one

                        dep = prev[arrival_time]
                        arr = line[departure_time]
                        try:
                            depTime = datetime.strptime(dep, date_format)
                            arrTime = datetime.strptime(arr, date_format)
                            t=(arrTime-depTime)
                            s=t.seconds
                        except:
                            s=0
                        detail = (prevStop,curStop,s,line[stop_sequence])
                        found = False
    #                     Check to see if this stop already exists in the servce
                        for stop in G.nodes[nodeId]['route']:
                            if stop[0] == detail[0] and stop[1] == detail[1]:
                                found = True
                                break
                        if not found:
    #                       get last
                            if len(G.nodes[nodeId]['route'])>0:
                                last = G.nodes[nodeId]['route'][-1]
    #                             if int(detail[3])-int(last[3]) ==1 and detail[0] == prev[1]: 

                                if detail[0] == last[1]: 
                                #This is the next stop in sequence AND follows from the last one
    #                                 print("Added xtra")
                                    G.nodes[nodeId]['route'].append(detail)
                                    G.add_edges_from([(line[stop_id],nodeId)])
                    #               Add edge from bus stop to route node
                            else:
    #                             print("Added 1st")
                                G.nodes[nodeId]['route'].append(detail)
                                G.add_edges_from([(line[stop_id],nodeId)])
            prev=line

    print("Done")       
    return G


# Below is a backup of the origional version of the code

# In[10]:


def removeNightNodes(G):
    toRemove=[]
    for id in G.nodes:
        node= G.nodes[id]
        if node['type'] == 'route':
            if node['last'] < datetime.strptime("06:00:00", date_format):
                print(id)
                toRemove.append(id)
                
    for id in toRemove:
        G.remove_node(id)
        
# removeNightNodes()


# In[11]:


# add walk
def addWalks(G):
    c=0
    for xID in G.nodes:
        x= G.nodes[xID]
        if x['type'] == 'stop':
            for yID in G.nodes:
                y = G.nodes[yID]
                if xID != yID:
                    if y['type'] == 'stop':
                        d=(haversine(x['stop_lat'],x['stop_lon'],y['stop_lat'],y['stop_lon']))*1000

#                       d is m
                        if d < 20 :

                            
#                             add edge
                            G.add_edges_from([(xID,yID)])
                            G.edges[xID,yID]['type'] ='walk'
                            t = (d *walk_speed_ms)/60 #t is mins
                            if (t < 1):
                                t=1

                            G.edges[xID,yID]['time'] = t


# addWalks()


# In[12]:


def saveGraph(G, gStops,cache):
    # save graph object to file
    pickle.dump(G, open(cache+'.graph.pickle', 'wb'))
    pickle.dump(gStops, open(cache+'.stops.pickle', 'wb'))
    
# saveGraph()


# In[13]:


def drawGraph():
    nx.draw(G, node_color = 'black')


# # Routing

# In[199]:


def measureRoute(route,board,disembark,vb=False):
    time=0
#     if vb:
#         print('Measuring route')
#         print(route)
#         print("Board: "+board)
#         print("Disembark: "+disembark)
    stops = G.nodes[route]['route']
    onBoard = False
    for stop in stops:
        if onBoard:
            time = time + stop[2]
#             if vb:
#                 print("Time : "+str(stop[2])+"="+str(time))
        if stop[0] == board:
#             if vb:
#                 print ("On board @" + stop[0])
            onBoard = True    
         
        if stop[1] == disembark:
#             check direction!
            if not onBoard:
                return float('inf')
            
#             if vb:
#                 print ("Disembark @" + stop[1])
            onBoard = False
            break
#     Calc frequency
    f = G.nodes[route]['first']
    l = G.nodes[route]['last']
    d = l-f
    f=d.seconds/G.nodes[route]['trips']
    time = time + (f)/2
    return time

    
    
def measureJourney(journey,verbose=False):
#     measure journey time in seconds
# add walking arcs...
    description=[]
    time=0
    c=0
    prev=None
    if verbose:
        description.append("Journey:")
    while c < len(journey):
        cNode = journey[c]
        if verbose:
            description.append(str(c)+ " : "+ cNode)
            if G.nodes[journey[c]]['type']=='stop':
                description.append(G.nodes[journey[c]]['stop_name'])

        if G.nodes[journey[c]]['type']=='route':
            time = time + (measureRoute(journey[c],journey[c-1],journey[c+1],vb=verbose)/60)
        if prev != None:
            edge = G.edges[prev,cNode]
            if 'type' in edge:
                if edge['type'] == 'walk':
                    time = time + edge['time']
        if verbose:          
            description.append(time)
        prev=cNode
        c=c+1
    return time,description

# def stopToLatLon(s_id):
# #     Convert a stop to lat/lon
#     r=(gStops.loc[gStops['stop_id'] == id].to_numpy()[0][3],gStops.loc[gStops['stop_id'] == s_id].to_numpy()[0][4])
    
def findRoute(start,end):
#     check start and end
    if start not in G.nodes:
        return "stop not found " + start,-1,[],""
    if end not in G.nodes:
        return "stop not found " + start,-1,[],""

    r=[]
    cutOff=2
    while len(r) ==0:
        r =list(nx.all_simple_edge_paths(G,source=start,target=end, cutoff=cutOff))
        cutOff = cutOff +2
        if cutOff ==10:
            return "not found",-1,[],""
    
    quickest = sys.float_info.max

    for path in r:
        journey=[]
        for step in path:
            if step[0] not in journey :
                journey.append(step[0])
            if step[1] not in journey:
                journey.append(step[1])

        t=measureJourney(journey)[0]
        if (t < quickest):
            quickest = t
            best = journey
            

    t,desc= measureJourney(best, verbose=True)
    
    return "found",quickest,best,desc





# In[203]:


def filterCentre(row):
    return point_in_polygon(Point(row['stop_lat'],row['stop_lon']),centrePoly)

def findStop(row,origin,rad):
    return haversine(row['stop_lat'],row['stop_lon'],origin[0],origin[1]) <= rad



def findPath(start, end=None, walk =0.5,centre= None):
    if end==None and centre == None:
        print("You must specify the end OR the city centre")
        return 
    
    startStops = gStops[gStops.apply(findStop, args=(start,walk),axis=1)]['stop_id'].values.tolist()

    if centre == None:
        print("Using end")
        endStops = gStops[gStops.apply(findStop,args=(end,walk), axis=1)]['stop_id'].values.tolist()
    else:
        print("Using centre")
        global centrePoly
        centrePoly = centre
        endStops = gStops[gStops.apply(filterCentre, axis=1)]['stop_id'].values.tolist()
    
    # Add start and end to graph

    G.add_node('start')
    G.nodes['start']['type'] = 'start'
    G.add_node('end')
    G.nodes['end']['type'] = 'end'

    for stop in startStops:
        d=haversine(start[0],start[1],G.nodes[stop]['stop_lat'],G.nodes[stop]['stop_lon'])*1000
        t=(d*walk_speed_ms)/60
        if t<1:
            t=1
        G.add_edges_from([('start',stop)])
        G.edges['start',stop]['type'] ='walk'
        G.edges['start',stop]['time'] = t
    
    for stop in endStops:
#         d=haversine(end[0],end[1],G.nodes[stop]['stop_lat'],G.nodes[stop]['stop_lon'])*1000
#         t=(d*walk_speed_ms)/60
#         if t<1:
#             t=1
        G.add_edges_from([('end',stop)])
        G.edges['end',stop]['type'] ='walk'
        G.edges['end',stop]['time'] = t

    r=findRoute('start','end')

    G.remove_node('start')
    G.remove_node('end')

    return r


# # Problem definition

# In[204]:


def setup(cache="",validAgency=[],boundingPoly=[]):
    global G
    global gStops
    global walk_speed_ms
    global date_format
    print("Setting up BusNet " + VERSION)
    
    date_format = '%H:%M:%S'
    gtfs_path = './itm_all_gtfs/'
    walk_speed_ms = 1.2
    
    if cache != "":
        G,gStops,res= load(cache)
        if res:
            print("Cache loaded")
            print(len(gStops))
            return
    print("Creating new graph!")
    print("Loading GTFS")
    validAgencyID,routes,routeIDs,trips,gStops,agency = loadGTFS(gtfs_path,validAgency,boundingPoly)
    print("Init graph")
    G = initGraph(gStops)
    print("Extracting times")
    extracted = loadStopTimes(G,gtfs_path)
    print("Processing stop times")
    G=processStopTimes(G, extracted,routes,agency,trips)
    print("Remove night nodes")
    removeNightNodes(G)
    print("Add walks")
    addWalks(G)
    if cache != "":
        print("Saving cache")
        saveGraph(G,gStops,cache)
    print("Graph created")
    
def getStops():
    return gStops

# START HERE!
print("BusNet4 imported")






