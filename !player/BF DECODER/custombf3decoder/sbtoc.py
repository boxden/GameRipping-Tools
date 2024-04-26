import sys
import os
from struct import unpack, pack
from binascii import hexlify, unhexlify
import zlib
from cStringIO import StringIO
from collections import OrderedDict
import Bundle

def read128(File):
   """Reads the next few bytes in a file as LEB128/7bit encoding and returns an integer"""
   result,i = 0,0
   while 1:
       byte=ord(File.read(1))
       result|=(byte&127)<<i
       if byte>>7==0: return result
       i+=7

def write128(integer):
   """Writes an integer as LEB128 and returns a byte string;
   roughly the inverse of read, but no files involved here"""
   bytestring=""
   while integer:
       byte=integer&127
       integer>>=7
       if integer: byte|=128
       bytestring+=chr(byte)
   return bytestring

def readNullTerminatedString(f):
   result=""
   while 1:
       char=f.read(1)
       if char=="\x00": return result
       result+=char

def unXOR(f):
   magic=f.read(4)
   if magic not in ("\x00\xD1\xCE\x00","\x00\xD1\xCE\x01"):
       f.seek(0) #the file is not encrypted
       return f

   f.seek(296)
   magic=[ord(f.read(1)) for i in xrange(260)] #bytes 257 258 259 are not used
   data=f.read()
   f.close()
   data2=[None]*len(data) #initalize the buffer
   for i in xrange(len(data)):
       data2[i]=chr(magic[i%257]^ord(data[i])^0x7b)
   return StringIO("".join(data2))

class EntryEnd(Exception):
   def __init__(self, value): self.value = value
   def __str__(self): return repr(self.value)

class Entry:
   #Entries always start with a 82 byte and always end with a 00 byte.
   #They have their own size defined right after that and are just one subelement after another.
   #This size contains all bytes after the size until (and including) the 00 byte at the end.
   #Use the size as an indicator when to stop reading and raise errors when nullbytes are missing.
   def __init__(self,toc): #read the data from file
##        if toc.read(1)!="\x82": raise Exception("Entry does not start with \x82 byte. Position: "+str(toc.tell()))
##        self.elems=OrderedDict()
##        entrySize=read128(toc)
##        endPos=toc.tell()+entrySize 
##        while toc.tell()<endPos-1: #-1 because of final nullbyte
##            content=Subelement(toc)
##            self.elems[content.name]=content
##        if toc.read(1)!="\x00": raise Exception("Entry does not end with \x00 byte. Position: "+str(toc.tell()))
       entryStart=toc.read(1)
       if entryStart=="\x82": #raise Exception("Entry does not start with \x82 byte. Position: "+str(toc.tell()))
           self.elems=OrderedDict()
           entrySize=read128(toc)
           endPos=toc.tell()+entrySize 
           while toc.tell()<endPos-1: #-1 because of final nullbyte
               content=Subelement(toc)
               self.elems[content.name]=content
           if toc.read(1)!="\x00": raise Exception("Entry does not end with \x00 byte. Position: "+str(toc.tell()))
       elif entryStart=="\x87":
####            self.elems=[]
##            entrySize=read128(toc)
##            endPos=toc.tell()+entrySize
####            print entrySize
##            print endPos
##            while toc.tell()<endPos: #-1 because of final nullbyte

           self.elems=toc.read(read128(toc)-1)
           toc.seek(1,1) #trailing null
       else:
           raise Exception("Entry does not start with \x82 or (rare) \x87 byte. Position: "+str(toc.tell()))



   def write(self, f): #write the data into file
       f.write("\x82")
       #Write everything into a buffer to get the size.
       buff=StringIO()
       #Write the subelements. Write in a particular order to compare output with original file.
       for key in self.elems:
           self.elems[key].write(buff)

       f.write(write128(len(buff.getvalue())+1)) #end byte
       f.write(buff.getvalue())
       f.write("\x00")
       buff.close()

   def showStructure(self,level=0):
       for key in self.elems:
           obj=self.elems[key]
           obj.showStructure(level+1)

class Subelement:
   #These are basically subelements of an entry.
   #It consists of type (1 byte), name (nullterminated string), data depending on type. 
   #However one such subelement may be a list type, containing several entries on its own.
   #Lists end with a nullbyte on their own; they (like strings) have their size prefixed as 7bit int.
   def __init__(self,toc): #read the data from file
       self.typ=toc.read(1)
       self.name=readNullTerminatedString(toc)

       if   self.typ=="\x0f": self.content=toc.read(16)
       elif self.typ=="\x09": self.content=unpack("Q",toc.read(8))[0]
       elif self.typ=="\x08": self.content=unpack("I",toc.read(4))[0]
       elif self.typ=="\x06": self.content=True if toc.read(1)=="\x01" else False
       elif self.typ=="\x02": self.content=toc.read(read128(toc))
       elif self.typ=="\x13": self.content=toc.read(read128(toc)) #the same as above with different content?
       elif self.typ=="\x10": self.content=toc.read(20) #sha1
       elif self.typ=="\x07": #string, length prefixed as 7bit int.
           self.content=toc.read(read128(toc)-1)
           toc.seek(1,1) #trailing null
       elif self.typ=="\x01": #lists
           self.listLength=read128(toc) #self
           entries=[]
           endPos=toc.tell()+self.listLength 
           while toc.tell()<endPos-1: #lists end on nullbyte
               entries.append(Entry(toc))
           self.content=entries
           if toc.read(1)!="\x00": raise Exception("List does not end with \x00 byte. Position: "+str(toc.tell()))
       else: raise Exception("Unknown type: "+hexlify(typ)+" "+str(toc.tell()))      

   def write(self,f): #write the data into file
       f.write(self.typ)
       f.write(self.name+"\x00")
       if   self.typ=="\x0f": f.write(self.content)
       elif self.typ=="\x10": f.write(self.content) #sha1
       elif self.typ=="\x09": f.write(pack("Q",self.content))
       elif self.typ=="\x08": f.write(pack("I",self.content))
       elif self.typ=="\x06": f.write("\x01" if self.content==True else "\x00")
       elif self.typ=="\x02": f.write(write128(len(self.content))+self.content)
       elif self.typ=="\x13": f.write(write128(len(self.content))+self.content) #the same as above with different content?
       elif self.typ=="\x07": #string
           f.write(write128(len(self.content)+1)+self.content+"\x00")
       elif self.typ=="\x01":
           #Write everything into a buffer to get the size.
           buff=StringIO()

           for entry in self.content:
               entry.write(buff)
           f.write(write128(len(buff.getvalue())+1)) #final nullbyte
           f.write(buff.getvalue())
           f.write("\x00")
           buff.close()


class Superbundle: #more about toc really
   def __init__(self,pathname):
       #make sure there is toc and sb
       self.fullpath,ext=os.path.splitext(pathname) #everything except extension
       self.filename=os.path.basename(self.fullpath) #the name without extension and without full path
       tocPath=pathname #toc or bundle
       tocPath,sbPath = self.fullpath+".toc",self.fullpath+".sb"
       if not (os.path.exists(tocPath) and os.path.exists(sbPath)): raise IOError("Could not find the sbtoc files.")
       try:
           toc=unXOR(open(tocPath,"rb"))
       except:
           raise Exception(pathname)
       self.entry=Entry(toc)
       toc.close()
