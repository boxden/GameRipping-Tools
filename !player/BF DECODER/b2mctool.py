# b2mctool.py
# drag & drop a Battlefield 2: Modern Combat .pak or .cat to unpack it
# this was written rather haphazardly so it may break on certain files, but i have not found any such file

from struct import unpack, pack
from os.path import split, splitext, join, isdir
from os import makedirs
from sys import argv
from io import BytesIO as bio

extless, ext = splitext(argv[1])
if ext.lower() == '.ark':
	outdir = argv[1] + ' dump'
	with open(argv[1], 'rb') as f:
		f.seek(-0x800, 2)
		oIndex, ui00_0x5D = unpack('2L', f.read(8))
		f.seek(oIndex*0x800)
		iFiles = unpack('L', f.read(4))[0]
		f.seek(0x800 - 4, 1)
		for iFile in range(iFiles):
			ui00_f, oData, datalen, pathlen = unpack('4L', f.read(16))
			path = f.read(pathlen).decode('ascii') # does NOT include terminator
			print(f'{ui00_f:08X} {oData:08X} {datalen:08X} {pathlen:08X} {path}')
			iBase = f.tell()
			padding = 4 - (iBase % 4) # padding has non-null bytes, but that's likely RAM trash from a lazy packer
			filefolders, filename = split(path)
			filefolders = join(outdir, filefolders)
			if not isdir(filefolders): makedirs(filefolders)
			f.seek(oData*0x800)
			open(join(filefolders, filename), 'wb').write(f.read(datalen))
			f.seek(iBase + (padding if padding else 4))
elif ext.lower() == '.cat': # tricky to unpack by itself, it's likely supposed to have an accompanying header file
	outdir = argv[1] + ' dump'
	with open(argv[1], 'rb') as f:
		while 1:
			try: pathlen = unpack('L', f.read(4))[0] # always div. by 4; includes all terminators in the string's aligned space, but not terminators outside
			except: break
			path = f.read(pathlen)
			zeropath = 0 in path
			if zeropath: path = path[:path.index(0)].decode('ascii')
			else: f.seek(4, 1); path = path.decode('ascii')
			filefolders, filename = split(path)
			filefolders = join(outdir, filefolders)
			if not isdir(filefolders): makedirs(filefolders)
			unk00, datalen = unpack('2L', f.read(8)) # if unk00 is 0 and path ascii is aligned, then path has no padding and flows seamlessly into unk00
			if not zeropath and unk00 != 1: f.seek(-0x4*3, 1); unk00, datalen = unpack('2L', f.read(8))
			print(f'{pathlen:08X} {unk00:08X} {datalen:08X} {path}')
			assert not (datalen % 4), f'Expected filesize of "{path}" to be divisible by 4.'
			open(join(filefolders, filename), 'wb').write(f.read(datalen))