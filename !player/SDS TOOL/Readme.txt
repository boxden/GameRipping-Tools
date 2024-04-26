SDSTool v1.0.1
SDS (Un)Packer

SDSTool allows you to pack und unpack Mafia II's SDS files.

Usage: sdstool <operation> [options] <input>

Unpacking sds
-------------
sdstool e -o <path to store extracted content to> <sds file>

Example:
sdstool e -o "<path to your Mafia installation>\pc\sds\city\greenfield" "<path to your Mafia installation>\pc\sds\city\greenfield.sds"

This extracts the contents of <path to your Mafia installation>\pc\sds\city\greenfield.sds and stores them in the folder
<path to your Mafia installation>\pc\sds\city\greenfield.
Additionally the command creates a stream map xml file which is needed to pack the sds again. I will not explain the format in detail, just
extract a few sds and have a look at their corresponding stream maps.
The default name for stream maps is Stream.xml.

It is strongly recommended to extract every sds to its own *empty* folder as several sds might contain files with same name.

** SDSTool silently overwrites any file in the target directory if it already exists. **

Packing sds
-----------
sdstool c -o <path to sds file> <path to stream map file>

Example:
sdstool c -o "<path to your Mafia installation>\pc\sds\city\greenfield.sds" "<path to your Mafia installation>\pc\sds\city\greenfield\Stream.xml"

This creates the sds <path to your Mafia installation>\pc\sds\city\greenfield.sds based on the description taken from the stream map file
<path to your Mafia installation>\pc\sds\city\greenfield\Stream.xml.

Note that you need to extract sds files with SDSTool in order to repack them since it needs a stream map which is currently not created by any other
tool (or create it by hand :p ).

** ALWAYS BACKUP YOUR ORIGINAL SDS FILES **.

Known Issues
------------
* SDSTool does not yet support encrypted sds (like sds\tables\tables.sds or several DLC sds). Any attempt to open them will crash SDSTool.
* Textures/Mipmaps have additional data in their headers between resource header and DDS header of 10/9 bytes length. SDSTool currently stores
  this data in the stream map when extracting textures. If anybody knows what this is good for, please inform me.

Credits
-------
Rick
s0beit
Guys over @ xentax
2K Games
anyone I forgot :o