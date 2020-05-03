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
from . import graph

import math

class Edge:
	def __init__ (self, vertex):
		self.vertex = vertex
		self.prev = None
		self.next = None
		self.twin = None
		self.poly = None
		self.ndx = 0
		
class Polygon:
	def __init__ (self, points, table, verts):
		#Create first edge... this is kind of bad
		prev = first = Edge (points[-1])
		prev.poly = self
		prev.ndx = points[-1]

		#Insert into the edge table
		if points[-1] not in table:
			table[points[-1]] = []
		table[points[-1]].append (prev)		
		
		for i in range (0, len (points) - 1):
			#Create a new edge
			edge = Edge (verts[points[i]])
			edge.poly = self
			edge.ndx = points[i]
			
			#Insert into the edge table
			if points[i] not in table:
				table[points[i]] = []
			table[points[i]].append (edge)
			
			#Link everything up
			edge.prev = prev
			prev.next = edge
			prev = edge
		
		#Finish the loop
		prev.next = first
		first.prev = prev
		#Store start edge
		self.head = first

class Export:
	def __init__ (self, config, context):
		self.cfg = config
		self.ctx = context
		
	def trace (self, text):
		if self.cfg.verbose is True:
			print (text)

	def main (self):
		from struct import pack
		scene = self.ctx.scene
		nmesh = 0
		ncgs = 0
		nwg = 0
		
		writ = {}
		bin = bytes ()
		geo = bytes ()
		cgs = bytes ()
		wg = bytes ()
		ents = bytes ()
		
		pref = os.path.splitext (self.cfg.filepath)[0]
		for o in scene.objects:
			if o.type != 'MESH':
				continue
			if o.hide_viewport:
				continue
			self.trace (o.name)
			
			#Figure out mesh ID
			if o.data in writ: id = writ[o.data]
			else: id = nmesh
			
			#Handle custom properties
			if o.get ('_RNA_UI'):
				self.trace ("Properties:")
				keys = o.keys ()
				
				#Copy all the keys into the entity dictionary
				edict = {}
				for k in keys:
					if '_RNA_UI' == k:
						continue
					if 'nowrite' == k:
						continue
					edict[k] = o[k]
				edict['name'] = o.name
				edict['origin'] = '{0} {1} {2}'.format (o.location[0], o.location[1], o.location[2])
				
				#Only used for entities with geometry
				if not 'nowrite' in keys:
					edict['mesh'] = id
				
				#Only objects with type properties to the entities list
				if "type" in edict:
					ents += bytes ('entity {0}\n'.format (edict['type']).encode ('utf-8'))
					for k, v in edict.items ():
						self.trace ("\t{0}: {1}".format (k, v));
						if 'type' == k:
							continue
						ents += bytes ('{0}: {1}\n'.format (k, v).encode ('utf-8'))
				
				#Do not write the geomtry
				#The properties will still be written though
				if 'nowrite' in keys:
					continue
		
			#Add object to world graph
			#TODO: Actually structure this into portals or a tree of some kind
			
			#Blender lets users specify different orders of euler angles. 
			#To make this sane, just convert the world matrix of the object 
			#into our own order and convert them into degrees and write
			#them in yaw-pitch-roll format. NB: Traum is X forward, Z up.
			def rad2deg (x):
				import math
				return -180.0*x/math.pi
				
			angles = o.matrix_world.to_euler ('ZYX')
			yaw = rad2deg (angles[2])
			pitch = rad2deg (angles[1])
			roll = rad2deg (angles[0])
			wg += pack ('<I', id)
			wg += pack ('<3f', o.location[0], o.location[1], o.location[2])
			wg += pack ('<3f', yaw, pitch, roll)
			wg += pack ('<3f', o.scale[0], o.scale[1], o.scale[2]);
			nwg += 1
	
			#Ensure this geometry is unique
			if o.data in writ:
				continue
			
			#Create a temporary mesh
			mesh = o.to_mesh ()
			if not mesh:
				self.trace ("{0} did not produce a mesh".format (o.name))
				continue
			
			#Ensure mesh has at least one material
			mat2poly = {}
			if len (mesh.materials) < 1:
				self.trace ('{0} has no materials! (using default)'.format (o.name))
				mat2poly["default"] = []
				use_default = True
			else:
				use_default = False

			#Sort polygons by material to minimise state changes
			for p in mesh.polygons:
				#Object has no materials, so drop everything into the default
				if True == use_default:
					mat2poly["default"].append (p)
					continue
				#Assign polygon to its material bucket
				#Blender appends the id of each user of a unique material to
				#its name. This is the only way I know how to get rid around it
				parts = mesh.materials[p.material_index].name.split ('.')
				key = parts[0]
				if key not in mat2poly:
					mat2poly[key] = []
				mat2poly[key].append (p)

			#Calculate bounding volume
			mins = [ math.inf, math.inf, math.inf]
			maxs = [-math.inf,-math.inf,-math.inf]
			for i in range (len (o.bound_box)):
				v = [o.bound_box[i][0], o.bound_box[i][1], o.bound_box[i][2]]
				for j in range (3):
					if v[j] < mins[j]: mins[j] = v[j];
					if v[j] > maxs[j]: maxs[j] = v[j];
			
			#Compute extents of AABB
			extents = [0, 0, 0]
			for i in range (3):
				extents[i] = (maxs[i] - mins[i])/2.0
			
			#Compute sphere
			centre = [0, 0, 0]
			d = [0, 0, 0]
			for i in range (3):
				centre[i] = extents[i] + mins[i]
				d[i] = maxs[i] - centre[i]
			radius = math.sqrt (d[0]*d[0] + d[1]*d[1] + d[2]*d[2])
			
			#Digest the polygons
			verts = pack ('<I3f3f1f',\
				len (mat2poly.items ()),\
				extents[0], extents[1], extents[2],\
				centre[0], centre[1], centre[2],\
				radius)

			from . import graph
			cmesh = graph.Cmesh ()	
			for key, polygons in mat2poly.items ():
				verts += pack ('<I', len (key))
				verts += key.encode ('utf-8')
				verts += pack ('<I', 3*len (polygons))
			
				#Pack vertices
				for p in polygons:
					#Ensure the geometry has been triangulated
					if p.loop_total != 3:
						#Degenerate
						if p.loop_total < 3:
							self.trace ('{0} has degenerate face!'.format (o.name))
							continue
						#More than 3
						self.trace ('{0} must have 3 vertices!'.format (o.name))
						continue
					
					#Package everything together
					points = []
					for i in range (p.loop_start, p.loop_start + p.loop_total):
						#Gather the data
						ndx = mesh.loops[i].vertex_index
						v = mesh.vertices[ndx].co
						uv = mesh.uv_layers.active.data[i].uv
						#Package it all up
						verts += pack ('<3f2f', v[0], v[1], v[2], uv[0], 1.0 - uv[1])
						#Collocate points
						points.append (ndx)
					
					#Add to collision graph
					cmesh.add_polygon (points)
			
			#Append all the data to the image
			geo += verts
			nmesh += 1
			
			#Stash index on the data so shared geometry gets written only once
			writ[o.data] = nmesh
			
			#Build and serialise the graph
			cmesh.build ()
			cg = bytes ()
			for v in mesh.vertices:
				cg += pack ('<3f', v.co[0], v.co[1], v.co[2])
			for p in cmesh.faces:
				points = []
				#Collocate points
				n = p.head
				while True:
					points.append (n.ndx)
					n = n.next
					if n is p.head:
						break
				cg += pack ('<4H', points[0], points[1], points[2], 0)		
			cg = pack ('<HH', len (mesh.vertices), len (cmesh.faces)) + cg
			
			#Append to the collision graph
			cgs += cg
			ncgs += 1
			
			#Done with the mesh data
			o.to_mesh_clear ()
		
		#Add headers for each section
		geo = pack ('<I', nmesh) + geo
		wg = pack ('<I', nwg) + wg
		cgs = pack ('<I', ncgs) + cgs
		ents = pack ('<I', len (ents)) + ents
		#Add the header
		ofs_verts = 6*4
		ofs_wg = ofs_verts + len (geo)
		ofs_cg = ofs_wg + len (wg)
		ofs_ents = ofs_cg + len (cg)
		MAGICK = 'SW3R'.encode ('utf-8')
		VERSION = 0x20200416
		header = MAGICK
		header += pack ('<IIIII', VERSION, ofs_verts, ofs_wg, ofs_cg, ofs_ents)
		bin = header + geo + wg + cgs + ents
		
		#Dump everything to disk
		level_path = bpy.path.ensure_ext (pref, '.level')
		with open (level_path, 'wb') as f:
			f.write (bin)
		
		self.trace ("Done!!!")
		return 0
