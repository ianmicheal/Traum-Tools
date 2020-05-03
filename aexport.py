# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation, either version 3
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#  All rights reserved.
#
# ##### END GPL LICENSE BLOCK #####

from math import radians, pi
import os
import bpy
from mathutils import *
from struct import pack
import math

class Export:
	def __init__ (self, config, context):
		self.cfg = config
		self.ctx = context
		
	def trace (self, text):
		if self.cfg.verbose is True:
			print (text)

	def write_mesh (self, armature, bonestate):
		scene = self.ctx.scene
		pref = os.path.splitext (self.cfg.filepath)[0]
		groups = armature.pose.bone_groups
		bones = bonestate.bones
		nbones = bonestate.nbones
		bone2index = bonestate.bone2index
		animset = bonestate.animset
		
		#Gather armature's children
		children = []
		for o in scene.objects:
			if o.parent != armature:
				continue
			children.append (o)
		
		#Ensure that there is work to do
		if 0 == len (children):
			return
			
		#Process materials
		materials = bytes ()
		nmaterials = 0
		mat2index = {}
		for o in children:
			#Create a temporary mesh
			mesh = o.to_mesh ()
			if not mesh:
				self.trace ("{0} did not produce a mesh".format (o.name).encode ('utf-8'))
				continue

			#Ensure mesh has a material
			if len (mesh.materials) != 1:
				self.trace ('{0} has no materials!'.format (o.name).encode ('utf-8'))
				return
			
			#Blender adds a user count to material name, so we have to strip it
			parts = mesh.materials[0].name.split ('.')
			key = parts[0]
			
			#Material names are unique
			if not key in mat2index:
				materials += pack ('<I', len (key))
				materials += key.encode ('utf-8')
				
				mat2index[key] = nmaterials;
				nmaterials += 1

			#Done with the mesh data
			o.to_mesh_clear ()
			
		#Digest each child into a nice binary form
		meshes = bytes ()
		nmeshes = 0
		distal = 0.0
		for o in children:
			#Create a temporary mesh
			mesh = o.to_mesh ()
			if not mesh:
				self.trace ("{0} did not produce a mesh".format (o.name).encode ('utf-8'))
				continue
			
			self.trace ("Gathering UVs...")
			uv_tbl = {}
			for p in mesh.polygons:
				#Ensure the geometry has been triangulated
				if p.loop_total != 3:
					#Degenerate
					if p.loop_total < 3:
						self.trace ('{0} has degenerate face!'.format (o.name))
						return
					#More than 3
					self.trace ('{0} must have 3 vertices!'.format (o.name))
					return
				
				#Save off each UV into a list per each vertex
				for i in range (p.loop_start, p.loop_start + p.loop_total):
					ndx = mesh.loops[i].vertex_index
					uv = mesh.uv_layers.active.data[i].uv
					if ndx in uv_tbl:
						if uv not in uv_tbl[ndx]:
							uv_tbl[ndx].append (uv)
					else:
						uv_tbl[ndx] = [uv]
			
			self.trace ("Generating vertices...")
			material = mat2index[mesh.materials[0].name.split ('.')[0]]
			npoints = 0
			points = bytes ()
			nverts = 0
			verts = bytes ()
			uv2index = {}
			for v in mesh.vertices:
				#Ensure that weight limit is not exceeded
				if len(v.groups) > 2:
					self.trace ("Limit of two weights per vertex exceeded")
					return
				
				#Ensure the weight is normalised
				sum = 0.0
				for g in v.groups:
					sum += g.weight
				
				if math.fabs (1.0 - sum) >= 1e-4:
					self.trace("Normalise your weights!");
					return
				
				#Bring the point into the bone spaces
				start = npoints
				for g in v.groups:
					import mathutils
					
					bone = armature.data.bones[o.vertex_groups[g.group].name]
					pos = bone.matrix_local.translation
					rot = bone.matrix
					delta = mathutils.Vector(v.co) - mathutils.Vector (pos)
					xyz = rot.inverted () @ delta
					
					points += pack ('<4f', xyz[0], xyz[1], xyz[2], g.weight)
					npoints += 1
					
					#Determine the most distal point
					dist = xyz.length
					if dist >= distal:
						distal = dist
					
				#Gather common vertex data
				n = v.normal
				count = npoints - start
				if 2 == len (v.groups):
					b0 = bone2index[o.vertex_groups[v.groups[0].group].name]
					b1 = bone2index[o.vertex_groups[v.groups[1].group].name]
				else:
					b0 = bone2index[o.vertex_groups[v.groups[0].group].name]
					b1 = b0
				
				#Generate the vertices derived from this point
				for uv in uv_tbl[v.index]:
					verts += pack ('<4f2f4H',\
								n[0], n[1], n[2], 0,\
								uv[0], uv[1],\
								start, count,\
								b0, b1)
					key = (uv.copy ().freeze (), v.index)
					uv2index[key] = nverts
					nverts += 1
			
			self.trace ("Generating indices...")
			from . import graph
			meshifier = graph.Meshifier ()
			for p in mesh.polygons:
				pts = []
				ids = []	
				for i in range (p.loop_start, p.loop_start + p.loop_total):
					uv = mesh.uv_layers.active.data[i].uv.copy ().freeze ()
					index = mesh.loops[i].vertex_index
					pts.append (index)
					ids.append (uv2index[(uv, index)])
				
				#Add the polygon into the adjacency graph
				meshifier.add_polygon (ids)
			
			#Decompose the model into strips and triangles
			strips, tris = meshifier.build ()
			
			#Package up the indices
			tstrips = bytes ()
			ntstrips = len (strips)
			for s in strips:
				strip = pack ('<I', len (s))
				print ('strip')
				for ndx in s:
					print (ndx)
					strip += pack ('<H', ndx[0])
				tstrips += strip
			
			islands = bytes ()
			nislands = len (tris)
			for ndx in tris:
				islands += pack ('<H', ndx[0])
			
			#Package everything together
			meshes += pack ('<5I', material, npoints, nverts, ntstrips, nislands)
			meshes += points + verts + tstrips + islands
			nmeshes += 1
			
			self.trace ('material: {0}'.format (material))
			self.trace ('points: {0}'.format (npoints))
			self.trace ('verts: {0}'.format (nverts))

			#Done with the mesh data
			o.to_mesh_clear ()
		
		#Assemble the file
		VERSION = 0x20200429
		header = 'RDKT'.encode ('utf-8')
		header += pack ('<3If2I', VERSION, animset, nbones, distal, nmaterials, nmeshes)
		bin = header + bones + materials + meshes
		
		#Dump everything to disk
		bin_path = bpy.path.ensure_ext (pref, '.tm')
		with open (bin_path, 'wb') as f:
			f.write (bin)
		
		self.trace ('distal: {0}'.format (distal))
		self.trace ("Mesh Done!!!")
		return 0
		
	def write_anim (self, armature, bonestate):
		#Set up some local state
		pref = os.path.splitext (self.cfg.filepath)[0]
		animset = bonestate.animset
		nbones = bonestate.nbones
		nframes = 0
		scene = self.ctx.scene
		fps = self.cfg.fps
		oldframe = scene.frame_current
		
		#Compute frame rate ratio
		#This is a bit weird. Blender symbolically works in frames, instead
		#of standard time, even in the API, so we have to kind of play its
		#game to get the proper sampling
		rate = scene.render.fps/fps
		
		#Iterate through the frames, saving off the pose for each one
		self.trace ('Gathering frame data...')
		trans = []
		frames = []
		
		i = scene.frame_start
		time = scene.frame_start
		num = 0
		
		#for i in range (scene.frame_start, scene.frame_end):
		while i < scene.frame_end: 
			#Set the frame
			i = math.floor (time)
			scene.frame_set (i, subframe=time - i)

			#Sample the elements
			frame = []
			bones= armature.pose.bones
			self.trace ('Frame {0} {1}'.format (num, time))
			for b in bones:
				angles = b.matrix_basis.to_euler ()
				frame.append (angles)
				self.trace ('\t{0} - {1}'.format (b.name, angles))
			frames.append (frame)
			
			#Sample the translation
			root = bones[0]
			origin = root.matrix_basis.translation
			trans.append (origin)
			self.trace ('\torigin: {0}'.format (origin))
			
			#Bump the time
			time += rate
			num += 1
		
		#Cache this for later
		nframes = len (frames)
		
		#Restore old frame
		scene.frame_set (oldframe)
			
		#Analyse the frames for compression opportunities
		self.trace ('Analysing frame data...')
		codes = nbones*[0]
		for i in range (nbones):
			codes[i] = 0
			prev = frames[0][i]
			#Go through each frame and take the difference in rotation between
			#the previous and current frame. If there is any component-wise
			#difference, then mark it down in a compression code
			for j in range (1, nframes):
				curr = frames[j][i]
				for k in range (3):
					if math.fabs (curr[k] - prev[k]) >= 1e-5:
						codes[i] |= 1<<k
				
				#Update comparison value for next frame
				prev = curr
			
			#Print the code for debugging
			flags = ''
			symbs = ['X', 'Y', 'Z']
			for j in range (3):
				if codes[i]&(1<<j):
					flags += symbs[j]
			if '' == flags:
				flags = '(elided)'
			self.trace ('\t{0} - {1}'.format (bones[i].name, flags))
		
		#Compose the binary data
		framedata = bytes ()
		for i in range (nframes):
			frame = frames[i]
			f = pack ('<f', trans[i][2])
			for j in range (nbones):
				#For now we just do all or nothing elision
				if 0 != i and 0 == codes[j]:
					continue
				
				#Write out the angles
				angles = 0
				for k in range (3):
					#Canonise the angles to 0 ~ 1023 (10 bits per axis)
					x = 512.0*frame[j][k]/math.pi
					while x >= 1024: x -= 1024	
					while x < 0: x += 1024
					
					#Write into angles
					angles |= int (x)<<(k*10)
				
				#Commit the bone to the frame
				f += pack ('<I', angles)
			
			#Append the frame to the binary data
			framedata += f
			
		#Package up the codes too
		codedata = bytes ()
		for c in codes:
			codedata += pack ('<B', c)
		
		#Use event markers to specify frame events
		self.trace ("Processing events...")
		eventlist = []
		nevents = 0
		for m in scene.timeline_markers:
			#Round up half a point for frames
			#Or maybe convert these to normal time instead?
			frame = math.floor (m.frame/rate + 0.5)
			
			#Clamp to 4 bytes so they can be used as 32 bit values
			if len (m.name) > 4:
				print ('WARNING: Truncating {0}...'.format (m.name))
			event = m.name.upper ()[:4].encode ('ascii')
			
			eventlist.append ((frame, event))
			nevents += 1
		
		#Sort the list by frame
		eventlist.sort (key=lambda e: e[0])
		
		#Create the binary data
		events = bytes ()
		for e in eventlist:
			self.trace ('\t{0} - {1}'.format (e[0], e[1]))
			events += pack ('<I', e[0]) + e[1] 
		
		#Assemble the file
		VERSION = 0x20200430
		header = 'RDTA'.encode ('utf-8')
		header += pack ('<5If', VERSION, animset, nevents, nbones, nframes, fps)
		bin = header + events + codedata + framedata
		
		#Dump everything to disk
		bin_path = bpy.path.ensure_ext (pref, '.ta')
		with open (bin_path, 'wb') as f:
			f.write (bin)
	
		self.trace ('{0}:'.format (bin_path))
		self.trace ('\tframes: {0}'.format (nframes))
		self.trace ('\tfps: {0}'.format (fps))
		self.trace ('\tsize: {0} bytes, {1} kib'.format (len (bin), len (bin)/1024))
		self.trace ("Anim Done!!!")
		
	def main (self):
		#Ensure selected object is an armature
		armature = self.ctx.active_object
		if armature.type != 'ARMATURE':
			#If the selected object isn't an armature, then make sure it's a mesh
			#then invoke `find_armature` on it to get the right thing
			if armature.type == 'MESH':
				armature = armature.find_armature ()
				if armature is None or armature.type != 'ARMATURE':
					self.trace ('Please select an armature or object parented to one!')
					return

		#Gather roots
		roots = []
		for b in armature.pose.bones:
			if b.parent is None:
				roots.append (b)
		
		#Only permit one root
		if len (roots) != 1:
			self.trace ('{0} must have a single root!'.format (armature.name))
		
		#Python does not let nested functions modify parent state
		#So stuff everything inside a container and pass it to the function
		class State:
			def __init__(self):
				self.bones = bytes ()
				self.nbones = 0
				self.bone2index = {}
				self.list = []
				self.animset = 0
		
		def write_bones_r (head, parent, depth, state):
			#Append the bone to the list
			xyz = head.matrix.translation
			state.bones += pack ('<3fI', xyz[0], xyz[1], xyz[2], parent)
			state.list.append (head)
			
			#Add bone to the remap table
			id = state.nbones
			state.bone2index[head.name] = id
			state.nbones += 1
			
			#Print a nice debug
			self.trace ('{0} < {1} {2} {3}'.format (id, parent, depth*'  ', head.name))
			
			#Recurse into children
			for ch in head.children:
				write_bones_r (ch, id, depth + 1, state)
		
		#Generate bones list
		bs = State ()
		write_bones_r (roots[0], 0, 0, bs)		
		
		#Generate animset
		import binascii		
		animset_data = ""
		for b in bs.list:
			animset_data += b.name
		
		bs.animset = binascii.crc32 (bytes (animset_data.encode ('ascii')))
		self.trace ('animset: {0}'.format (bs.animset))
		
		#Write out mesh if requested
		if self.cfg.domesh:
			self.write_mesh (armature, bs)

		#Write out animation if requested
		if self.cfg.doanim:
			self.write_anim (armature, bs)
