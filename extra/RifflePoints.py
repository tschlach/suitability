import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import math 
#import numpy as np     #Doesnt' work for IronPython. Need to download stuff... Look at this link: 
        #https://stevebaer.wordpress.com/2011/06/27/numpy-and-scipy-in-rhinopython/
        #http://www.grasshopper3d.com/forum/topics/scipy-and-numpy

#x = Thalweg
#y = Division lengths for points along centerline
#z = Right Bank 
#u = Left Bank


class Centerline(object):
    def __init__(self, crvCenterline, crvBankRight, crvBankLeft, lenDivision):
        #****makes a list of each variable. In order, but not attributed to each point. 
        #****may want to pull everything under point info
        self.Thalweg = crvCenterline
        self.lenDivision = lenDivision
        self.BankRight = crvBankRight
        self.BankLeft = crvBankLeft
        self.length = rs.CurveLength(crvCenterline)             #Length
        self.start = rs.CurveStartPoint(crvCenterline)          #3D Start Point
        self.end = rs.CurveEndPoint(crvCenterline)              #3D End Point
        self.drop = self.start[2] - self.end[2]                 #Elevation Drop across length of curve
        self.points = rs.DivideCurveLength(crvCenterline, lenDivision, True, True) #Divide curve into lengths X (,X,,)
        self.riffles = []      

        #Set up Riffles
        self.createRiffles(lenDivision)
        
        #get existing conditions values
        #?????Should we do this after the getIdealRiffleDesign so that we can vary the window
        #?????based on the ideal riffle length? Answer: No. Ideal Riffle Design Requires Valley Slope.
        self.getSlopes(2,5)                #(,X) X is important and factors into variances alot. Need to not hard code in.
        self.getIdealRiffleDesign(.5, 10, crvCenterline)
        self.getBendRatios(5)
        self.getBendRatios2(5)

        #calculate deisgn values
        
        
        #*****************************************
        #can now link this to the design iterator (justin) for riffle width and depth, using bank width as the riffle
        #width and plugging in a flowrate. 
        #*****************************************


     
        #Error handling/Print Values
        # for i in range(len(self.points)):
        #     print(self.riffles[i].station)
            # print(self.riffles[i].bend_ratio)
        #     print(self.riffles[i].slopeAtPoint)
        #     print(self.riffles[i].bank_width)
        #     print(self.riffles[i].pt)
        #     print(self.riffles[i].ptBankRight)
        #     print(self.riffles[i].ptBankLeft)
        #     print("----------")
        
    def getIdealRiffleDesign(self, riffle_drop_min, riffle_length_min, cl): 
        ##need an additional variable - that is able to be reset

        points = []
        interval = 1

        #split curve into 0.1 increments to be sampled
        points = rs.DivideCurveLength(cl, interval, True, True)

        #Calculate Ideal riffle design for each stream point
        for i in self.riffles:
            check = False
            count = 0
            riffle_drop = riffle_drop_min       #Initial drop test
            riffle_length = riffle_length_min   #Initial length test
            

            #loop through sizing scenarios
            while check == False and count < 35:
                
                length = None
                rUSInvert = i.pt.Z
                rDSInvert = rUSInvert - riffle_drop
                pool_station_start = i.station + riffle_length

                #Calc Pool length by when it gets to next point on centerline at same elevation
                #Get index for starting point
                iStartPoint = int(round(i.station, 1) / interval)

                print('Find Elevation', iStartPoint, len(points), rDSInvert)
                
                for j in range(iStartPoint, len(points)):
                    if points[j].Z < rDSInvert:
                        pool_length = (j-1) * interval - pool_station_start
                        pt = points[j]
                        print(pt)
                        print (j, pool_length, i.station, pool_station_start, points[j].Z)
                        break


                if pool_length >= 1.5 * riffle_length:
                    i.geometry = "Riffle"
                    i.riffle.length = riffle_length
                    i.riffle.drop = riffle_drop
                    i.riffle.slope = riffle_drop / riffle_length
                    i.riffle.station_end = i.station + i.riffle.length
                    
                    i.pool.length = pool_length
                    i.pool.station_start = i.riffle.station_end
                    i.pool.station_end = i.station + i.riffle.length + i.pool.length
                    check = True
                else:
                    if riffle_length < 30:
                        riffle_length += 5
                        count +=1
                    elif riffle_drop < 2:
                        riffle_length = riffle_length_min
                        riffle_drop += 0.25
                        count +=1
                    else:
                        i.geometry = "Neither"
                        check = True
                    #!!!NEED TO ADD IN CASCADE
        return


    def createRiffles(self, lenDivision):
        for i in range(len(self.points)):
            station = i * lenDivision
            self.riffles.append(StreamPoint(self.points[i], self.Thalweg, self.BankRight, self.BankLeft, station, lenDivision))
        return
    
    def getBendRatios2(self, t):
        for i in range(len(self.riffles)-t):
            self.riffles[i].bend_ratio2 = rs.CurveCurvature(self.Thalweg, self.riffles[i].parameter)[3]
        return
        
    def getBendRatios(self, t):
        array_bend_ratio = []

        #get first list of bend_ratios
        for i in range(len(self.riffles)-t):
      
            p = horizontal_distance(self.riffles[i].ptBankLeft, self.riffles[i+t].ptBankLeft)
            l = abs(self.riffles[i].station - self.riffles[i+t].station)
            p_diff = abs(p - l)
            
            self.riffles[i].bend_ratio = p_diff
            array_bend_ratio.append(p_diff)

        #Normalize
        old_min = min(array_bend_ratio)
        old_range = max(array_bend_ratio) - old_min
        
        new_min = 0
        new_range = 1 - new_min

        for i in range(len(self.points)-t):
            n = self.riffles[i].bend_ratio
            new_bend_ratio = (n - old_min) / old_range * new_range + new_min
            self.riffles[i].bend_ratio = new_bend_ratio
        return
    
    #getSlopes defines the *discrete* slopes of the line, based on the straight distance between points on the line
    def getSlopes(self, winChannel, winValley):
        
        #Channel Slope
        for i in range(len(self.riffles)):
            t1 = min([i, winChannel])
            t2 = min([len(self.riffles)-i-1, winChannel])
            sta1 = self.riffles[i - t1].station
            sta2 = self.riffles[i + t2].station
            pt1_z = self.riffles[i - t1].pt.Z
            pt2_z = self.riffles[i + t2].pt.Z
            self.riffles[i].channel_slope = (pt1_z - pt2_z)/(sta1 - sta2)
                   

        #Valley Slope
        for i in range(len(self.riffles)): 
            t1 = min([i, winValley])
            t2 = min([len(self.riffles)-i-1, winValley])
            sta1 = self.riffles[i - t1].station
            sta2 = self.riffles[i + t2].station
            pt1_z = self.riffles[i - t1].elevBankLow
            pt2_z = self.riffles[i + t2].elevBankLow
            self.riffles[i].valley_slope = (pt1_z - pt2_z)/(sta1 - sta2)
        return


class StreamPoint(object):
    """docstring for ClassName"""
    #Notes to think about:
    # -Does difference in left/right bank elevation matter in design?

    def __init__(self, point, crvCenterline, crvBankRight, crvBankLeft, station, lenDivision):
        #Define Initial Values
        self.pt = point
        self.parameter = rs.CurveClosestPoint(crvCenterline, point)     #Parameter (t) for point on centerline
        self.tangent = rs.CurveTangent(crvCenterline, self.parameter)
        self.slopeAtPoint = self.tangent[2]
        self.channel_slope = None
        self.valley_slope = None
        self.station = station
        self.bend_ratio = None
        self.bend_ratio2 = None
        self.index = int(self.station/lenDivision)
        self.suitability = 0
        self.use = None                    #1 = Riffle, 0 = Don't Use, -1 = Pool (pool points not usedd for now)

        #Bank Information
        self.ptBankRight = rs.EvaluateCurve(crvBankRight, rs.CurveClosestPoint(crvBankRight, self.pt))
        self.ptBankLeft = rs.EvaluateCurve(crvBankLeft, rs.CurveClosestPoint(crvBankLeft, self.pt))
        self.bank_width = horizontal_distance(self.ptBankRight, self.ptBankLeft)
        self.BankRightIncision = self.ptBankRight.Z - self.pt.Z 
        self.BankLeftIncision = self.ptBankLeft.Z - self.pt.Z 
        self.elevBankLow = min(self.ptBankLeft.Z, self.ptBankRight.Z)
        self.valley_slope = None

        #Proposed Riffle Design Information
        self.riffle = RifflePoint()
        self.pool = PoolPoint()
        self.geometry = None
        
        #project Thalweg to Horizontal Plane
        crvCenterlineHoriz = rs.CopyObject(crvCenterline)
        rs.ScaleObject(crvCenterlineHoriz, (0,0,0), (1,1,0))
        self.parameterHorizontal = rs.CurveClosestPoint(crvCenterlineHoriz, point)
 
class RifflePoint(object):
    
    def __init__(self):
        #Proposed Riffle Design Information
        self.length = None
        self.slope = None
        self.drop = None
        self.width = None     #Calc based on Bank Width
        self.depth = None
        self.station_start = None 
        self.station_end = None
    
class PoolPoint(object):

    def __init__(self):
        #Proposed Riffle Design Information
        self.length = None
        self.slope = None
        self.drop = None
        self.width = None     #Calc based on Bank Width
        self.station_start = None
        self.station_end = None
               


def horizontal_distance(pt1, pt2):
    distance = math.sqrt(math.pow(pt2.X - pt1.X, 2) + math.pow(pt2.Y - pt1.Y, 2)) 
    return distance



#x is set as curve in centerline class
crvRifflePoints = Centerline(crvThalweg, crvRightBank, crvLeftBank, interval)

    

# attr = []
# attr.append('pt.Z')
# attr.append('parameter')
# attr.append('tangent')
# attr.append('slopeAtPoint')
# attr.append('channel_slope')
# attr.append('valley_slope')
# attr.append('station')
# attr.append('bend_ratio')
# attr.append('ptBankRight')
# attr.append('ptBankLeft')
# attr.append('bank_width')
# attr.append('BankRightIncision')
# attr.append('BankLeftIncision')
# attr.append('elevBankLow')
# attr.append('valley_slope')
# attr.append('riffle_length')
# attr.append('riffle_slope')
# attr.append('riffle_drop')
# attr.append('riffle_width')
# attr.append('geometry')

