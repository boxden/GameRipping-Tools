#  Tested with any python version between 2.7.3 32-bit - 2.7.15 32-bit
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
#Choose where you dumped the files and where to put the decoded audio:
dumpDirectory       = r"E:\bf3 dump"
targetDirectory     = r"E:/bf3 decoded"

#Download Zench's tool so the script can handle EALayer3.
ealayer3Path        = r"C:\ealayer3-0.7.0-win32\ealayer3.exe" #https://bitbucket.org/Zenchreal/ealayer3/downloads

#These paths are relative to the dumpDirectory. They don't need to be changed.
ebxFolder           = r"bundles\ebx\sound" #files are not restricted to the Sound folder in bf4. As a result it will seem that the script does nothing for a while.
chunkFolder         = r"chunks"
chunkFolder2        = r"bundles\chunks" #if the chunk is not found in the first folder, use this on


#There was a console game for Frostbite 2 in which the byte order of the chunk ids given in the ebx was changed a bit
#so it did not match the ids in the chunk folders. See also http://www.bfeditor.org/forums/index.php?showtopic=15780&view=findpost&p=106500
#Unless you know for sure that the ids are obfuscated, don't set this to True.
ChunkIdObfuscation      =False
obfuscationPermutation  =[3,2,1,0,5,4,7,6,8,9,10,11,12,13,14,15]

##############################################################
##############################################################
from binascii import hexlify
from struct import unpack,pack
import os
from cStringIO import StringIO
import subprocess
from ctypes import *

#let's see if XAS and Speex exist
try:
    xas = cdll.LoadLibrary("xas")
    def decodeXas(chunkPath, target, samplesOffset):
        makeLongDirs(target)
        try:
            process = subprocess.Popen(["xas_decode.exe",chunkPath,target,str(samplesOffset)],stderr=subprocess.PIPE,startupinfo=startupinfo)
            process.communicate() #this should set the returncode
            if process.returncode:
                print process.stderr.readlines()
        except:
            print "Error executing Xas_decode."

    def decodePcm(chunkPath, target, samplesOffset):
        makeLongDirs(target)
        xas.swapEndianPcm(chunkPath, target, samplesOffset)
    print "XAS1 dll detected."
except:
    def decodeXas(chunkPath, target, samplesOffset):
        print "Skipping XAS1 due to missing dll."
    def decodePcm(chunkPath, target, samplesOffset):
        print "Skipping PCM due to missing dll."
    print "XAS1 dll not detected."

try:
    speex = cdll.LoadLibrary("easpeex")
    def decodeSpeex(chunkPath, target, samplesOffset):
        makeLongDirs(target)
        speex.decode(chunkPath, target, samplesOffset)
    print "EASpeex dll detected."
except:
    def decodeSpeex(chunkPath, target, samplesOffset):
        print "Skipping Speex due to missing dll."
    print "EASpeex dll not detected."    

#By default Python opens a new EALayer3 window for a split second and puts focus on it. This info makes no window show up at all.
startupinfo = subprocess.STARTUPINFO()
startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startupinfo.wShowWindow = subprocess.SW_HIDE

try:
    #make sure EALayer3 exists by calling it once without arguments 
    subprocess.Popen([ealayer3Path],startupinfo=startupinfo)
    def decodeEaLayer(chunkPath, target, samplesOffset):
        makeLongDirs(target)
        process = subprocess.Popen([ealayer3Path,chunkPath,"-i",str(samplesOffset),"-o",target,"-s","all"], stderr=subprocess.PIPE,startupinfo=startupinfo)
        process.communicate() #this should set the returncode
        if process.returncode:
            print process.stderr.readlines()
    print "EALayer3 tool detected."
except:
    def decodeEaLayer(chunkPath, target, samplesOffset):
        print "Skipping EALayer3 due to missing tool."
    print "EALayer3 tool not detected."

    

def unpackBE(typ,data): return unpack(">"+typ,data)

def makeLongDirs(path):
    #create folders if necessary and return the file handle
    #first of all, create one folder level manully because makedirs might fail
    path=os.path.normpath(path)
    pathParts=path.split("\\")
    manualPart="\\".join(pathParts[:2])
    if not os.path.isdir(manualPart): os.makedirs(manualPart)
    
    #now handle the rest, including extra long path names
    folderPath=lp(os.path.dirname(path))
    if not os.path.isdir(folderPath): os.makedirs(folderPath)
    

def open2(path,mode="rb"):
    if mode=="wb": makeLongDirs(path)
    return open(lp(path),mode)

def lp(path): #long pathnames
    if len(path)<=247 or path=="" or path[:4]=='\\\\?\\': return path
    return unicode('\\\\?\\' + os.path.normpath(path))


def hasher(keyword): #32bit FNV-1 hash with FNV_offset_basis = 5381 and FNV_prime = 33
    hash = 5381
    for byte in keyword:
        hash = (hash*33) ^ ord(byte)
    return hash & 0xffffffff # use & because Python promotes the num instead of intended overflow
class Header:
    def __init__(self,varList):
        self.absStringOffset     = varList[0]  ## absolute offset for string section start
        self.lenStringToEOF      = varList[1]  ## length from string section start to EOF
        self.numGUID             = varList[2]  ## number of external GUIDs
        self.numInstanceRepeater = varList[3]  ## total number of instance repeaters
        self.numGUIDRepeater     = varList[4]  ## instance repeaters with GUID
        self.unknown             = varList[5]
        self.numComplex          = varList[6]  ## number of complex entries
        self.numField            = varList[7]  ## number of field entries
        self.lenName             = varList[8]  ## length of name section including padding
        self.lenString           = varList[9]  ## length of string section including padding
        self.numArrayRepeater    = varList[10]
        self.lenPayload          = varList[11] ## length of normal payload section; the start of the array payload section is absStringOffset+lenString+lenPayload
class FieldDescriptor:
    def __init__(self,varList,keywordDict):
        self.name            = keywordDict[varList[0]]
        self.type            = varList[1]
        self.ref             = varList[2] #the field may contain another complex
        self.offset          = varList[3] #offset in payload section; relative to the complex containing it
        self.secondaryOffset = varList[4]
        if self.name=="$": self.offset-=8
class ComplexDescriptor:
    def __init__(self,varList,keywordDict):
        self.name            = keywordDict[varList[0]]
        self.fieldStartIndex = varList[1] #the index of the first field belonging to the complex
        self.numField        = varList[2] #the total number of fields belonging to the complex
        self.alignment       = varList[3]
        self.type            = varList[4]
        self.size            = varList[5] #total length of the complex in the payload section
        self.secondarySize   = varList[6] #seems deprecated
class InstanceRepeater:
    def __init__(self,varList):
        self.complexIndex    = varList[0] #index of complex used as the instance
        self.repetitions     = varList[1] #number of instance repetitions
class arrayRepeater:
    def __init__(self,varList):
        self.offset          = varList[0] #offset in array payload section
        self.repetitions     = varList[1] #number of array repetitions
        self.complexIndex    = varList[2] #not necessary for extraction
class Complex:
    def __init__(self,desc,dbxhandle):
        self.desc=desc
        self.dbx=dbxhandle #lazy
    def get(self,name):
        pathElems=name.split("/")
        curPos=self
        if pathElems[-1].find("::")!=-1: #grab a complex
            for elem in pathElems:
                try:
                    curPos=curPos.go1(elem)
                except Exception,e:
                    raise Exception("Could not find complex with name: "+str(e)+"\nFull path: "+name+"\nFilename: "+self.dbx.trueFilename)
            return curPos
        #grab a field instead
        for elem in pathElems[:-1]:
            try:
                curPos=curPos.go1(elem)
            except Exception,e:
                raise Exception("Could not find complex with name: "+str(e)+"\nFull path: "+name+"\nFilename: "+self.dbx.trueFilename)
        for field in curPos.fields:
            if field.desc.name==pathElems[-1]:
                return field
            
        raise Exception("Could not find field with name: "+name+"\nFilename: "+self.dbx.trueFilename)

    def go1(self,name): #go once
        for field in self.fields:
            if field.desc.type in (0x0029, 0xd029,0x0000,0x0041):
                if field.desc.name+"::"+field.value.desc.name == name:
                    return field.value
        raise Exception(name)


class Field:
    def __init__(self,desc,dbx):
        self.desc=desc
        self.dbx=dbx
    def link(self):
        if self.desc.type!=0x0035: raise Exception("Invalid link, wrong field type\nField name: "+self.desc.name+"\nField type: "+hex(self.desc.type)+"\nFile name: "+self.dbx.trueFilename)
        
        if self.value>>31:
            extguid=self.dbx.externalGUIDs[self.value&0x7fffffff]
            
            for existingDbx in dbxArray:
                if existingDbx.fileGUID==extguid[0]:
                    for guid, instance in existingDbx.instances:
                        if guid==extguid[1]:
                            return instance
                    

            f=valid(inputFolder+guidTable[extguid[0]]+".ebx")
##            print guidTable[extguid[0]]
            dbx=Dbx(f)
            dbxArray.append(dbx)
            for guid, instance in dbx.instances:
                if guid==extguid[1]:
                    return instance
            raise nullguid("Nullguid link.\nFilename: "+self.dbx.trueFilename)
        elif self.value!=0:
            for guid, instance in self.dbx.instances:
                if guid==self.dbx.internalGUIDs[self.value-1]:
                    return instance
        else:
            raise nullguid("Nullguid link.\nFilename: "+self.dbx.trueFilename)

        raise Exception("Invalid link, could not find target.")

    def getlinkguid(self):
        if self.desc.type!=0x0035: raise Exception("Invalid link, wrong field type\nField name: "+self.desc.name+"\nField type: "+hex(self.desc.type)+"\nFile name: "+self.dbx.trueFilename)

        if self.value>>31:
            return "".join(self.dbx.externalGUIDs[self.value&0x7fffffff])
        elif self.value!=0:
            return self.dbx.fileGUID+self.dbx.internalGUIDs[self.value-1]
        else:
            raise nullguid("Nullguid link.\nFilename: "+self.dbx.trueFilename)
    def getlinkname(self):
        if self.desc.type!=0x0035: raise Exception("Invalid link, wrong field type\nField name: "+self.desc.name+"\nField type: "+hex(self.desc.type)+"\nFile name: "+self.dbx.trueFilename)

        if self.value>>31:
            return guidTable[self.dbx.externalGUIDs[self.value&0x7fffffff][0]]+"/"+self.dbx.externalGUIDs[self.value&0x7fffffff][1]
        elif self.value!=0:
            return self.dbx.trueFilename+"/"+self.dbx.internalGUIDs[self.value-1]
        else:
            raise nullguid("Nullguid link.\nFilename: "+self.dbx.trueFilename)
    

         
def valid(fname):
    f=open2(fname,"rb")
    if f.read(4) not in ("\xCE\xD1\xB2\x0F","\x0F\xB2\xD1\xCE"):
        f.close()
        raise Exception("nope")
    return f

class nullguid(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

numDict={0xC12D:("Q",8),0xc0cd:("B",1) ,0x0035:("I",4),0xc10d:("I",4),0xc14d:("d",8),0xc0ad:("?",1),0xc0fd:("i",4),0xc0bd:("b",1),0xc0ed:("h",2), 0xc0dd:("H",2), 0xc13d:("f",4)}

class Stub:
    pass


class Dbx:
    def __init__(self, f, relPath):
        #metadata
        magic=f.read(4)
        if magic=="\xCE\xD1\xB2\x0F":   self.unpack=unpack
        elif magic=="\x0F\xB2\xD1\xCE": self.unpack=unpackBE
        else: raise ValueError("The file is not ebx: "+relPath)
        self.trueFilename=""
        self.header=Header(self.unpack("3I6H3I",f.read(36)))
        self.arraySectionstart=self.header.absStringOffset+self.header.lenString+self.header.lenPayload
        self.fileGUID=f.read(16)
        while f.tell()%16!=0: f.seek(1,1) #padding
        self.externalGUIDs=[(f.read(16),f.read(16)) for i in xrange(self.header.numGUID)]
        self.keywords=str.split(f.read(self.header.lenName),"\x00")
        self.keywordDict=dict((hasher(keyword),keyword) for keyword in self.keywords)
        self.fieldDescriptors=[FieldDescriptor(self.unpack("IHHii",f.read(16)), self.keywordDict) for i in xrange(self.header.numField)]
        self.complexDescriptors=[ComplexDescriptor(self.unpack("IIBBHHH",f.read(16)), self.keywordDict) for i in xrange(self.header.numComplex)]
        self.instanceRepeaters=[InstanceRepeater(self.unpack("2H",f.read(4))) for i in xrange(self.header.numInstanceRepeater)] 
        while f.tell()%16!=0: f.seek(1,1) #padding
        self.arrayRepeaters=[arrayRepeater(self.unpack("3I",f.read(12))) for i in xrange(self.header.numArrayRepeater)]

        #payload
        f.seek(self.header.absStringOffset+self.header.lenString)
        self.internalGUIDs=[]
        self.instances=[] # (guid, complex)
        nonGUIDindex=0
        self.isPrimaryInstance=True

        for i, instanceRepeater in enumerate(self.instanceRepeaters):
            for repetition in xrange(instanceRepeater.repetitions):
                #obey alignment of the instance; peek into the complex for that
                while f.tell()%self.complexDescriptors[instanceRepeater.complexIndex].alignment!=0: f.seek(1,1)

                #all instances after numGUIDRepeater have no guid
                if i<self.header.numGUIDRepeater:
                    instanceGUID=f.read(16)
                else:
                    #just numerate those instances without guid and assign a big endian int to them.
                    instanceGUID=pack(">I",nonGUIDindex)
                    nonGUIDindex+=1
                self.internalGUIDs.append(instanceGUID)

                inst=self.readComplex(instanceRepeater.complexIndex,f,True)
                inst.guid=instanceGUID

                if self.isPrimaryInstance: self.prim=inst
                self.instances.append( (instanceGUID,inst))
                self.isPrimaryInstance=False #the readComplex function has used isPrimaryInstance by now

        f.close()

        #if no filename found, use the relative input path instead
        #it's just as good though without capitalization
        if self.trueFilename=="":
            self.trueFilename=relPath


    def readComplex(self, complexIndex, f, isInstance=False):
        complexDesc=self.complexDescriptors[complexIndex]
        cmplx=Complex(complexDesc,self)
        cmplx.offset=f.tell()
                     
        cmplx.fields=[]
        #alignment 4 instances require subtracting 8 for all field offsets and the complex size
        obfuscationShift=8 if (isInstance and cmplx.desc.alignment==4) else 0
        
        for fieldIndex in xrange(complexDesc.fieldStartIndex,complexDesc.fieldStartIndex+complexDesc.numField):
            f.seek(cmplx.offset+self.fieldDescriptors[fieldIndex].offset-obfuscationShift)
            cmplx.fields.append(self.readField(fieldIndex,f))
        
        f.seek(cmplx.offset+complexDesc.size-obfuscationShift)
        return cmplx

    def readField(self,fieldIndex,f):
        fieldDesc = self.fieldDescriptors[fieldIndex]
        field=Field(fieldDesc,self)
        
        if fieldDesc.type in (0x0029, 0xd029,0x0000,0x8029):
            field.value=self.readComplex(fieldDesc.ref,f)
        elif fieldDesc.type==0x0041:
            arrayRepeater=self.arrayRepeaters[self.unpack("I",f.read(4))[0]]
            arrayComplexDesc=self.complexDescriptors[fieldDesc.ref]

            f.seek(self.arraySectionstart+arrayRepeater.offset)
            arrayComplex=Complex(arrayComplexDesc,self)
            arrayComplex.fields=[self.readField(arrayComplexDesc.fieldStartIndex,f) for repetition in xrange(arrayRepeater.repetitions)]
            field.value=arrayComplex
            
        elif fieldDesc.type in (0x407d, 0x409d):
            startPos=f.tell()
            stringOffset=self.unpack("i",f.read(4))[0]
            if stringOffset==-1:
                field.value="*nullString*"
            else:
                f.seek(self.header.absStringOffset+stringOffset)
                field.value=""
                while 1:
                    a=f.read(1)
                    if a=="\x00": break
                    else: field.value+=a
                f.seek(startPos+4)

                if self.isPrimaryInstance and fieldDesc.name=="Name" and self.trueFilename=="": self.trueFilename=field.value
                   
        elif fieldDesc.type in (0x0089,0xc089): #incomplete implementation, only gives back the selected string
            compareValue=self.unpack("i",f.read(4))[0] 
            enumComplex=self.complexDescriptors[fieldDesc.ref]

            if enumComplex.numField==0:
                field.value="*nullEnum*"
            for fieldIndex in xrange(enumComplex.fieldStartIndex,enumComplex.fieldStartIndex+enumComplex.numField):
                if self.fieldDescriptors[fieldIndex].offset==compareValue:
                    field.value=self.fieldDescriptors[fieldIndex].name
                    break
        elif fieldDesc.type==0xc15d:
            field.value=f.read(16)
##        elif fieldDesc.type == 0xc13d: ################################
##            field.value=formatfloat(self.unpack("f",f.read(4))[0])
        elif fieldDesc.type==0x417d:
            field.value=f.read(8)
        else:
            (typ,length)=numDict[fieldDesc.type]
            num=self.unpack(typ,f.read(length))[0]
            field.value=num
        
        return field
        
    def decode(self):
        if not self.prim.desc.name=="SoundWaveAsset": return

        histogram=dict() #count the number of times each chunk is used by a variation to obtain the right index

        Chunks=[]
        for i in self.prim.get("$::SoundDataAsset/Chunks::array").fields:
            chnk=Stub()
            Chunks.append(chnk)
            chnk.ChunkId=i.value.get("ChunkId").value
            
            if ChunkIdObfuscation: chnk.ChunkId="".join([chnk.ChunkId[permute] for permute in obfuscationPermutation])
                
            chnk.ChunkSize=i.value.get("ChunkSize").value

            

        Variations=[]


        Segments=[]
        for seg in self.prim.get("Segments::array").fields:
            Segment=Stub()
            Segments.append(Segment)
            Segment.SamplesOffset = seg.value.get("SamplesOffset").value
            Segment.SeekTableOffset = seg.value.get("SeekTableOffset").value
            Segment.SegmentLength = seg.value.get("SegmentLength").value


        
        for var in self.prim.get("RuntimeVariations::array").fields:
            Variation=Stub()
            Variations.append(Variation)
            Variation.ChunkIndex=var.value.get("ChunkIndex").value
            Variation.FirstSegmentIndex=var.value.get("FirstSegmentIndex").value
            Variation.SegmentCount=var.value.get("SegmentCount").value

            Variation.Segments=Segments[Variation.FirstSegmentIndex:Variation.FirstSegmentIndex+Variation.SegmentCount]
            Variation.ChunkId=hexlify(Chunks[Variation.ChunkIndex].ChunkId)
            Variation.ChunkSize=Chunks[Variation.ChunkIndex].ChunkSize
        
            #find the appropriate index
            #the index from the Variations array can get large very fast
            #instead, make my own index starting from 0 for every chunkIndex
            if Variation.ChunkIndex in histogram: #has been used previously already
                Variation.Index=histogram[Variation.ChunkIndex]
                histogram[Variation.ChunkIndex]+=1
            else:
                Variation.Index=0
                histogram[Variation.ChunkIndex]=1
        
        #everything is laid out neatly now
        #Variation fields: ChunkId, ChunkSize, Index, ChunkIndex, SeekTablesSize, FirstLoopSegmentIndex, LastLoopSegmentIndex, Segments
        #Variation.Segments fields: SamplesOffset, SeekTableOffset, SegmentLength

        ChunkHandles=dict() #for each ebx, keep track of all file handles

        chunkErrors=set() #
        for Variation in Variations:
            try:
                f=ChunkHandles[Variation.ChunkId]
            except:
                try:
                    f=open2(chunkFolder+Variation.ChunkId+".chunk")
                    currentChunkName=chunkFolder+Variation.ChunkId+".chunk"
                except IOError:
                    try:
                        f=open2(chunkFolder2+Variation.ChunkId+".chunk")
                        currentChunkName=chunkFolder2+Variation.ChunkId+".chunk"
                    except:
                        print "Chunk does not exist: "+Variation.ChunkId+" "+self.trueFilename
                        chunkErrors.add("Chunnk does not exist: "+Variation.ChunkId+" "+self.trueFilename)
                        continue #do NOT return, instead print the messages at the very end
                ChunkHandles[Variation.ChunkId]=f


            for ijk in xrange(len(Variation.Segments)):
                Segment=Variation.Segments[ijk]
                f.seek(Segment.SamplesOffset)
                magic=f.read(4)
                
                if magic!="\x48\x00\x00\x0c":
                    continue
                    raise Exception("Wrong XAS magic.")

                audioType=ord(f.read(1)) #0x14 is XAS, 0x16 is EALayer3, 0x13 is XMA, 0x12 is PCM
                target=os.path.join(targetDirectory,self.trueFilename)+" "+str(Variation.ChunkIndex)+" "+str(Variation.Index)+" "+str(ijk)
                #os.path.exists(targetPath): return True
                    #print "allready got it"

                if audioType==0x16: #EALayer3
                    target+=".mp3"
                    decodeEaLayer(currentChunkName, target, Segment.SamplesOffset)
                elif audioType==0x19: #Speex
                    target+=".wav"
                    decodeSpeex(currentChunkName, target, Segment.SamplesOffset)
                elif audioType==0x14: #XAS1
                    target+=".wav"
                    decodeXas(currentChunkName, target, Segment.SamplesOffset)
                elif audioType==0x12: #16bit big endian PCM
                    target+=".wav"
                    decodePcm(currentChunkName, target, Segment.SamplesOffset)
                else:
                    print "Unknown audio segment (type "+hex(audioType)+"): "+Variation.ChunkId+" "+self.trueFilename

        for key in ChunkHandles:
            ChunkHandles[key].close()
        print self.trueFilename
###############
        for message in chunkErrors:
            print "chunkerror" + message
###########
def riffHeader(samplingRate, numChannels, isFloat):
    header="RIFFabcdWAVEfmt (\x00\x00\x00" #replace abcd later
    extended=0xfffe #always use the extended header to make things simpler
    numFormat,numSize=(3,4) if isFloat else (1,2)
    header+=pack("HHllHHHHlH", extended, numChannels, samplingRate, numChannels*samplingRate*numSize,
                 numChannels*numSize, numSize*8, 22, numSize*8, (1<<numChannels)-1, numFormat)
    header+="\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x008\x9bqfact\x04\x00\x00\x00"
    header+=pack("l",numSize)
    header+="dataABCD"
    return header

#make the paths absolute and normalize the slashes
ebxFolder,chunkFolder,chunkFolder2 = [os.path.normpath(dumpDirectory+"\\"+path)+"\\" for path in (ebxFolder, chunkFolder, chunkFolder2)]
targetDirectory=os.path.normpath(targetDirectory) #it's an absolute path already



def main():
    for dir0, dirs, ff in os.walk(ebxFolder):
        for fname in ff:
            if fname[-4:]!=".ebx": continue
            absPath=os.path.join(dir0,fname)
            relPath=absPath[len(ebxFolder):-4]
            
            f=open(lp(absPath),"rb")
            try:
                dbx=Dbx(f,relPath)
                f.close()
            except ValueError as msg:
                f.close()
                if str(msg).startswith("The file is not ebx: "):
                    continue
                else: asdf
            dbx.decode()


main()
