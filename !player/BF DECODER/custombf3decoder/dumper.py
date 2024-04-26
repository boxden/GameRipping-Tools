import sbtoc
import Bundle
import os
from binascii import hexlify,unhexlify
from struct import pack,unpack
from cStringIO import StringIO
import sys
import zlib

##Adjust paths here. The script doesn't overwrite existing files so set tocRoot to the patched files first,
##then run the script again with the unpatched ones to get all files at their most recent version.

catName=r"E:\Games\Battlefield 4\Data\cas.cat" #use "" or r"" if you have no cat; doing so will make the script ignore patchedCatName
patchedCatName=r"E:\Games\Battlefield 4\Update\Patch\Data\cas.cat" #used only when tocRoot contains "Update"

tocRoot=r"E:\Games\Battlefield 4\Data\Win32"
##tocRoot=r"C:\Program Files (x86)\Origin Games\Battlefield 3\Data\Win32"

outputfolder="E:/bf3 dump"


#mohw stuff:

##catName=r"C:\Program Files (x86)\Origin Games\Medal of Honor Warfighter\Data\cas.cat"
##patchedCatName=r"C:\Program Files (x86)\Origin Games\Medal of Honor Warfighter\Update\Patch\Data\cas.cat"
##
##tocRoot=r"C:\Program Files (x86)\Origin Games\Medal of Honor Warfighter\Data"
##
##outputfolder="D:/hexing/mohw dump123/"



#####################################
#####################################

#zlib (one more try):
#Files are split into pieces which are then zlibbed individually (prefixed with compressed and uncompressed size)
#and finally glued together again. Non-zlib files on the other hand have no prefix about size, they are just the payload.
#The archive or file does not declare zlib/nonzlib, making things really complicated. I think the engine actually uses
#ebx and res to figure out if a chunk is zlib or not. However, res itself is zlibbed already; in mohw ebx is zlibbed too.
#In particular mohw crashes when delivering a non-zlibbed ebx file.
#Prefixing the payload with two identical ints containing the payload size makes mohw work again so the game really deduces
#compressedSize==uncompressedSize => uncompressed payload.

#some thoughts without evidence:
#It's possible that ebx/res zlib is slightly different from chunk zlib.
#Maybe for ebx/res, compressedSize==uncompressedSize always means an uncompressed piece.
#Whereas for chunks (textures in particular), there are mip sizes to consider
#e.g. first piece of a mip is always compressed (even with compressedSize==uncompressedSize) but subsequent pieces of a mip may be uncompressed.

def zlibb(f, size):
   #if the entire file is < 10 bytes, it must be non zlib
   if size<10: return f.read(size)

   #interpret the first 10 bytes as fb2 zlib stuff
   uncompressedSize,compressedSize=unpack(">ii",f.read(8))
   magic=f.read(2)
   f.seek(-10,1)

   #sanity check: compressedSize may be just random non-zlib payload.
   if compressedSize>size-8: return f.read(size)
   if compressedSize<=0 or uncompressedSize<=0: return f.read(size)

   #another sanity check with a very specific condition:
   #when uncompressedSize is different from compressedSize, then having a non-zlib piece makes no sense.
   #alternatively one could just let the zlib module try to handle this.
   #It's tempting to compare uncompressedSize<compressedSize, but there are indeed cases when
   #the uncompressed payload is smaller than the compressed one.
   if uncompressedSize!=compressedSize and magic!="\x78\xda":
       return f.read(size)

   outStream=StringIO()
   pos0=f.tell()
   while f.tell()<pos0+size-8:
       uncompressedSize,compressedSize=unpack(">ii",f.read(8)) #big endian

       #sanity checks:
       #The sizes may be just random non-zlib payload; as soon as that happens,
       #abandon the whole loop and just give back the full payload without decompression
       if compressedSize<=0 or uncompressedSize<=0:
           f.seek(pos0)
           return f.read(size)
       #likewise, make sure that compressed size does not exceed the size of the file
       if f.tell()+compressedSize>pos0+size:
           f.seek(pos0)
           return f.read(size)

       #try to decompress
       if compressedSize!=uncompressedSize:
           try:    outStream.write(zlib.decompress(f.read(compressedSize)))
           except: outStream.write(f.read(compressedSize))
       else:
           #if compressed==uncompressed, one might be tempted to think that it is always non-zlib. It's not.
           magic=f.read(2)
           f.seek(-2,1)
           if magic=="\x78\xda":
               try:    outStream.write(zlib.decompress(f.read(compressedSize)))
               except: outStream.write(f.read(compressedSize))
           else:
               outStream.write(f.read(compressedSize))

   data=outStream.getvalue()
   outStream.close()
   return data


def zlibIdata(bytestring):
   return zlibb(StringIO(bytestring),len(bytestring))

def hex2(num):
   #take int, return 8byte string
   a=hex(num)
   if a[:2]=="0x": a=a[2:]
   if a[-1]=="L": a=a[:-1]
   while len(a)<8:
       a="0"+a
   return a

class Stub(): pass


class Cat:
   def __init__(self,catname):
       cat2=open(catname,"rb")
       cat=sbtoc.unXOR(cat2)

       self.casfolder=os.path.dirname(catname)+"\\"
       cat.seek(0,2)
       catsize=cat.tell()
       cat.seek(16)
       self.entries=dict()
       while cat.tell()<catsize:
           entry=Stub()
           sha1=cat.read(20)
           entry.offset, entry.size, entry.casnum = unpack("<III",cat.read(12))
           self.entries[sha1]=entry
       cat.close()
       cat2.close()

   def grabPayload(self,entry):
       cas=open(self.casfolder+"cas_"+("0"+str(entry.casnum) if entry.casnum<10 else str(entry.casnum))+".cas","rb")
       cas.seek(entry.offset)
       payload=cas.read(entry.size)
       cas.close()
       return payload
   def grabPayloadZ(self,entry):
       cas=open(self.casfolder+"cas_"+("0"+str(entry.casnum) if entry.casnum<10 else str(entry.casnum))+".cas","rb")
       cas.seek(entry.offset)
       payload=zlibb(cas,entry.size)
       cas.close()
       return payload



def open2(path,mode):
   #create folders if necessary and return the file handle

   #first of all, create one folder level manully because makedirs might fail
   pathParts=path.split("\\")
   manualPart="\\".join(pathParts[:2])
   if not os.path.isdir(manualPart): os.makedirs(manualPart)

   #now handle the rest, including extra long path names
   folderPath=lp(os.path.dirname(path))
   if not os.path.isdir(folderPath): os.makedirs(folderPath)
   return open(lp(path),mode)

##    return StringIO()


def lp(path): #long pathnames
   if path[:4]=='\\\\?\\' or path=="" or len(path)<=247: return path
   return unicode('\\\\?\\' + os.path.normpath(path))

resTypes={
   0x5C4954A6:".itexture",
   0x2D47A5FF:".gfx",
   0x22FE8AC8:"",
   0x6BB6D7D2:".streamingstub",
   0x1CA38E06:"",
   0x15E1F32E:"",
   0x4864737B:".hkdestruction",
   0x91043F65:".hknondestruction",
   0x51A3C853:".ant",
   0xD070EED1:".animtrackdata",
   0x319D8CD0:".ragdoll",
   0x49B156D4:".mesh",
   0x30B4A553:".occludermesh",
   0x5BDFDEFE:".lightingsystem",
   0x70C5CB3E:".enlighten",
   0xE156AF73:".probeset",
   0x7AEFC446:".staticenlighten",
   0x59CEEB57:".shaderdatabase",
   0x36F3F2C0:".shaderdb",
   0x10F0E5A1:".shaderprogramdb",
   0xC6DBEE07:".mohwspecific"
}


def dump(tocName,outpath):
   try:
       toc=sbtoc.Superbundle(tocName)
   except IOError:
       return

   sb=open(toc.fullpath+".sb","rb")

   chunkPathToc=os.path.join(outpath,"chunks")+"\\"
   #
   bundlePath=os.path.join(outpath,"bundles")+"\\"
   ebxPath=bundlePath+"ebx\\"
   dbxPath=bundlePath+"dbx\\"       
   resPath=bundlePath+"res\\"
   chunkPath=bundlePath+"chunks\\"


   if "cas" in toc.entry.elems and toc.entry.elems["cas"].content==True:
       #deal with cas bundles => ebx, dbx, res, chunks. 
       for tocEntry in toc.entry.elems["bundles"].content: #id offset size, size is redundant
           sb.seek(tocEntry.elems["offset"].content)
           bundle=sbtoc.Entry(sb)

           for listType in ["ebx","dbx","res","chunks"]: #make empty lists for every type to get rid of key errors(=> less indendation)
               if listType not in bundle.elems:
                   bundle.elems[listType]=Stub()
                   bundle.elems[listType].content=[]

           for entry in bundle.elems["ebx"].content: #name sha1 size originalSize
               casHandlePayload(entry,ebxPath+entry.elems["name"].content+".ebx")

           for entry in bundle.elems["dbx"].content: #name sha1 size originalSize
               if "idata" in entry.elems: #dbx appear only idata if at all, they are probably deprecated and were not meant to be shipped at all.
                   out=open2(dbxPath+entry.elems["name"].content+".dbx","wb")
                   if entry.elems["size"].content==entry.elems["originalSize"].content:
                       out.write(entry.elems["idata"].content)
                   else:          
                       out.write(zlibIdata(entry.elems["idata"].content))

                   out.close()

           for entry in bundle.elems["res"].content: #name sha1 size originalSize resType resMeta
               if entry.elems["resType"].content not in resTypes: #unknown res file type
                   casHandlePayload(entry,resPath+entry.elems["name"].content+" "+hexlify(entry.elems["resMeta"].content)+".unknownres"+hex2(entry.elems["resType"].content))
               elif entry.elems["resType"].content in (0x4864737B,0x91043F65,0x49B156D4,0xE156AF73,0x319D8CD0): #these 5 require resMeta. OccluderMesh might too, but it's always 16*ff
                   casHandlePayload(entry,resPath+entry.elems["name"].content+" "+hexlify(entry.elems["resMeta"].content)+resTypes[entry.elems["resType"].content])
               else:
                   casHandlePayload(entry,resPath+entry.elems["name"].content+resTypes[entry.elems["resType"].content])

           for entryNum in xrange(len(bundle.elems["chunks"].content)): #id sha1 size, chunkMeta::meta
               entry=bundle.elems["chunks"].content[entryNum]
               entryMeta=bundle.elems["chunkMeta"].content[entryNum]
               if entryMeta.elems["meta"].content=="\x00":
                   firstMip=""
               else:
                   firstMip=" firstMip"+str(unpack("B",entryMeta.elems["meta"].content[10])[0])

               casHandlePayload(entry,chunkPath+hexlify(entry.elems["id"].content)+firstMip+".chunk")


       #deal with cas chunks defined in the toc. 
       for entry in toc.entry.elems["chunks"].content: #id sha1
           casHandlePayload(entry,chunkPathToc+hexlify(entry.elems["id"].content)+".chunk")



   else:
       #deal with noncas bundles
       for tocEntry in toc.entry.elems["bundles"].content: #id offset size, size is redundant

           if "base" in tocEntry.elems: continue #Patched noncas bundle. However, use the unpatched bundle because no file was patched at all.
##          So I just skip the entire process and expect the user to extract all unpatched files on his own.

           sb.seek(tocEntry.elems["offset"].content)

           if "delta" in tocEntry.elems:
               #Patched noncas bundle. Here goes the hilarious part. Take the patched data and glue parts from the unpatched data in between.
               #When that is done (in memory of course) the result is a new valid bundle file that can be read like an unpatched one.

               deltaSize,DELTAAAA,nulls=unpack(">IIQ",sb.read(16))
               deltas=[]
               for deltaEntry in xrange(deltaSize/16):
                   delta=Stub()
                   delta.size,delta.fromUnpatched,delta.offset=unpack(">IIQ",sb.read(16))
                   deltas.append(delta)

               bundleStream=StringIO() #here be the new bundle data
               patchedOffset=sb.tell()

##unpatched: C:\Program Files (x86)\Origin Games\Battlefield 3\Update\Xpack2\Data\Win32\Levels\XP2_Palace\XP2_Palace.sb/toc
##patched:   C:\Program Files (x86)\Origin Games\Battlefield 3\Update\Patch\Data\Win32\Levels\XP2_Palace\XP2_Palace.sb/toc
#So at this point I am at the patched file and need to get the unpatched file path. Just how the heck...
#The patched toc itself contains some paths, but they all start at win32.
#Then again, the files are nicely named. I.e. XP2 translates to Xpack2 etc.

               xpNum=os.path.basename(toc.fullpath)[2] #XP2_Palace => 2
               unpatchedPath=toc.fullpath.lower().replace("patch","xpack"+str(xpNum))+".sb"

               unpatchedSb=open(unpatchedPath,"rb")

               for delta in deltas:
                   if not delta.fromUnpatched:
                       bundleStream.write(sb.read(delta.size))
                   else:
                       unpatchedSb.seek(delta.offset)
                       bundleStream.write(unpatchedSb.read(delta.size))
               unpatchedSb.close()
               bundleStream.seek(0)          
               bundle=Bundle.Bundle(bundleStream)
               sb2=bundleStream

           else:
               sb.seek(tocEntry.elems["offset"].content)
               bundle=Bundle.Bundle(sb)
               sb2=sb

           for entry in bundle.ebxEntries:
               noncasHandlePayload(sb2,entry,ebxPath+entry.name+".ebx")

           for entry in bundle.resEntries:
               if entry.resType not in resTypes: #unknown res file type
                   noncasHandlePayload(sb2,entry,resPath+entry.name+" "+hexlify(entry.resMeta)+".unknownres"+hex2(entry.resType))
               elif entry.resType in (0x4864737B,0x91043F65,0x49B156D4,0xE156AF73,0x319D8CD0):
                   noncasHandlePayload(sb2,entry,resPath+entry.name+" "+hexlify(entry.resMeta)+resTypes[entry.resType])
               else:
                   noncasHandlePayload(sb2,entry,resPath+entry.name+resTypes[entry.resType])


           for entry in bundle.chunkEntries:
               if entry.meta=="\x00":
                   firstMip=""
               else:
                   firstMip=" firstMip"+str(unpack("B",entry.meta[10])[0])
               noncasHandlePayload(sb2,entry,chunkPath+hexlify(entry.id)+firstMip+".chunk")

       #deal with noncas chunks defined in the toc
       for entry in toc.entry.elems["chunks"].content: #id offset size
           entry.offset,entry.size = entry.elems["offset"].content,entry.elems["size"].content #to make the function work
           noncasHandlePayload(sb,entry,chunkPathToc+hexlify(entry.elems["id"].content)+".chunk")
   sb.close()


def noncasHandlePayload(sb,entry,outPath):
   if os.path.exists(lp(outPath)): return
   print outPath
   sb.seek(entry.offset)
   out=open2(outPath,"wb")
   if "originalSize" in vars(entry):
       if entry.size==entry.originalSize:
           out.write(sb.read(entry.size))
       else:
           out.write(zlibb(sb,entry.size))
   else:
       out.write(zlibb(sb,entry.size))
   out.close()


if catName!="":
   cat=Cat(catName)

   if "update" in tocRoot.lower():
       cat2=Cat(patchedCatName)
       def casHandlePayload(entry,outPath): #this version searches the patched cat first
           if os.path.exists(lp(outPath)): return #don't overwrite existing files to speed up things
           print outPath
           if "originalSize" in entry.elems:
               compressed=False if entry.elems["size"].content==entry.elems["originalSize"].content else True #I cannot tell for certain if this is correct. I do not have any negative results though.
           else:
               compressed=True
           if "idata" in entry.elems:
               out=open2(outPath,"wb")
               if compressed: out.write(zlibIdata(entry.elems["idata"].content))
               else:          out.write(entry.elems["idata"].content)

           else:        
               try:
                   catEntry=cat2.entries[entry.elems["sha1"].content]
                   activeCat=cat2
               except:
                   catEntry=cat.entries[entry.elems["sha1"].content]
                   activeCat=cat
               out=open2(outPath,"wb") #don't want to create an empty file in case an error pops up
               if compressed: out.write(activeCat.grabPayloadZ(catEntry))
               else:          out.write(activeCat.grabPayload(catEntry))

           out.close()


   else:
       def casHandlePayload(entry,outPath): #this version uses the unpatched cat only
           if os.path.exists(lp(outPath)): return #don't overwrite existing files to speed up things
           print outPath
           if "originalSize" in entry.elems:
               compressed=False if entry.elems["size"].content==entry.elems["originalSize"].content else True #I cannot tell for certain if this is correct. I do not have any negative results though.
           else:
               compressed=True
           if "idata" in entry.elems:
               out=open2(outPath,"wb")
               if compressed: out.write(zlibIdata(entry.elems["idata"].content))
               else:          out.write(entry.elems["idata"].content)
           else:        
               catEntry=cat.entries[entry.elems["sha1"].content]
               out=open2(outPath,"wb") #don't want to create an empty file in case an error pops up
               if compressed: out.write(cat.grabPayloadZ(catEntry))
               else:          out.write(cat.grabPayload(catEntry))
           out.close()



def main():
   for dir0, dirs, ff in os.walk(tocRoot):
       for fname in ff:
           if fname[-4:]==".toc":
               print fname
               fname=dir0+"\\"+fname
               dump(fname,outputfolder)

outputfolder=os.path.normpath(outputfolder)
main()
