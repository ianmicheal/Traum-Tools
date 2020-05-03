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

bl_info = {
	"name": "Traum",
	"author": "Sifting",
	"version": (1, 1, 0),
	"blender": (2, 82, 0),
	"location": "File > Export > Traum",
	"description": "Exports geometry to Traum",
	"wiki_url": "",
	"category": "Import-Export"}


import bpy
from bpy.props import BoolProperty
from bpy.props import FloatProperty
from bpy.props import StringProperty
from bpy.props import EnumProperty

#
#Level Exporter
#
class ExportTraum(bpy.types.Operator):
	bl_idname = "export_scene.traum"
	bl_label = "Export Level to Traum"

	filename_ext = ".level"
	filter_glob: StringProperty (default="*.level", options={'HIDDEN'})
	filepath: StringProperty(subtype='FILE_PATH')
	verbose: BoolProperty(
		name="Verbose",
		description="Spews debugging info to console",
		default=True)
		
	def execute(self, context):
		from . import texport
		imp = texport.Export (self, context)
		imp.main ()
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.fileselect_add(self)
		return {'RUNNING_MODAL'}

def menu_func_level(self, context):
	self.layout.operator(ExportTraum.bl_idname, text="Traum Level (.level)")
	
#
#Model exporter
#
class ExportTraumModel(bpy.types.Operator):
	bl_idname = "export_scene.traum_model"
	bl_label = "Export Model to Traum"

	filename_ext = ".tm"
	filter_glob: StringProperty (default="*.tm;*.ta", options={'HIDDEN'})
	filepath: StringProperty(subtype='FILE_PATH')
	verbose: BoolProperty(
		name="Verbose",
		description="Spews debugging info to console",
		default=True)

	domesh: BoolProperty(
		name="Export Mesh",
		description="Writes out mesh data, if present",
		default=True)

	doanim: BoolProperty(
		name="Export Animation",
		description="Writes out animation data, if present",
		default=True)
		
	fps: FloatProperty(
		name="Framerate",
		description="(Affects Filesize) Sets the frames per second to sample",
		min=2.0, max=60.0,
		default=30.0,
	)
	def execute(self, context):
		from . import aexport
		imp = aexport.Export (self, context)
		imp.main ()
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.fileselect_add(self)
		return {'RUNNING_MODAL'}
		
def menu_func_model(self, context):
	self.layout.operator(ExportTraumModel.bl_idname, text="Traum Model (.tm/.ta)")
	
def register():
	bpy.utils.register_class(ExportTraum)
	bpy.utils.register_class(ExportTraumModel)
	bpy.types.TOPBAR_MT_file_export.append(menu_func_level)
	bpy.types.TOPBAR_MT_file_export.append(menu_func_model)

def unregister():
	bpy.utils.unregister_class(ExportTraum)
	bpy.utils.unregister_class(ExportTraumModel)
	bpy.types.TOPBAR_MT_file_export.remove(menu_func_level)
	bpy.types.TOPBAR_MT_file_export.remove(menu_func_model)

if __name__ == "__main__":
	register()
