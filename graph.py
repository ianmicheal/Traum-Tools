import math

class Edge:
	def __init__ (self):
		self.prev = None
		self.next = None
		self.twin = None
		self.poly = None
		self.attribute = None
		self.ndx = 0
		
class Polygon:
	def __init__ (self, points, table, attributes):
		#Create first edge... this is kind of bad
		prev = first = Edge ()
		prev.poly = self
		prev.ndx = points[-1]
		if attributes:
			prev.attribute = attributes[-1]
				
		#Insert into the edge table
		if points[-1] not in table:
			table[points[-1]] = []
		table[points[-1]].append (prev)		
		
		for i in range (0, len (points) - 1):
			#Create a new edge
			edge = Edge ()
			edge.poly = self
			edge.ndx = points[i]
			if attributes:
				edge.attribute = attributes[i]
			
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
		
		self.neighbours = 0
		
class Graph:
	def __init__ (self):
		self.faces = []
		self.tbl = {}
		self.built = False
		
	def add_polygon (self, loop, attributes = None):
		self.faces.append (Polygon (loop, self.tbl, attributes))
		
	def remove_polygon (self, facep):
		#Remove links to this face from the neighbours
		edge = face.head.next
		while edge is not face.head:
			if edge.twin is not None:
				edge.twin.poly.neighbours -= 1
				edge.twin.twin = None
				edge.twin = None
			
			edge = edge.next
		
		#Zero out the neighbours
		face.neighbours = 0
	
	def build (self):
		#If the graph has already been built, then there is no work to do
		if True == self.built:
			return
	
		#Build collision graph links
		linked = 0
		for p in self.faces:
			n = p.head
			while True:
				if n.next.ndx in self.tbl:
					#Search all edges that reference this vertex
					for e in self.tbl[n.next.ndx]:
						a = n.ndx
						b = n.next.ndx
						c = e.ndx
						d = e.next.ndx
						if a == d and b == c:
							n.twin = e
							e.twin = n
							linked += 1
							break
				
				#Advance to the next edge
				n = n.next
				if n is p.head:
					break
		
		#Compute the number of neighbours for each face
		for p in self.faces:
			edge = p.head
			while True:
				if edge.twin is not None:
					p.neighbours += 1
				
				edge = edge.next
				if edge is p.head:
					break
		
		#Mark graph as built
		self.built = True
		
		#Debugging information
		print ('Graph Linked: {0}'.format (linked))
	
class Meshifier(Graph):
	def build (self):
		#Ensure that the graph is built
		super ().build ()
			
		def minimal (h):
			if len (h) == 0:
				return None
			return min (h, key = lambda e: e.neighbours)
		
		#A min heap might be faster here, but for now this works fine
		heap = self.faces.copy ()
		
		#Begin the algorithm proper
		strips = []
		islands = []
		while True:
			#Pull out the lowest neighbour'd face
			face = minimal (heap)
			if None is face:
				break
			
			#Sort islands into their own set
			if 0 == face.neighbours:
				islands.append (face)
				continue
			
			#Walk through the neighbours for as long as possible to assemble
			#a nice tristrip
			print ('Generating edge list...')
			strip = []
			while True:
				#Remove this face from the heap
				face.neigbhours = -1
				heap.remove (face)
				#Pick the neighbour face with the most other neighbours
				count = 0
				next = None
				next_face = None
				next_twin = None
				edge = face.head
				while True:
					#Ensure that this edge is connected to an adjacent face
					twin = edge.twin
					if twin is not None:			
						#Save this edge if its the most connected
						other = twin.poly	
						degree = other.neighbours
						if degree >= count:
							count = degree
							next_face = other
							next_twin = twin
							next = edge
						
						#Unlink this face from neighbour
						other.neighbours -= 1
						twin.twin = None
						edge.twin = None
						
					#Search the next edge
					edge = edge.next
					if edge is face.head:
						break
				
				#Continue into the selected neighbour until we exhaust
				#all possible connections
				if next is None:
					break
				
				#Relink edge and append it to the list
				next.twin = next_twin
				strip.append (next)
				
				#Advance into the chosen face
				face = next_face	
			
			#Digest the strip into index values
			print ("Digesting edge list...")
			indices = []
			curr = strip[0]
			
			#Append the initial indices into the list
			indices.append ((curr.next.ndx, curr.next.attribute))
			indices.append ((curr.prev.ndx, curr.prev.attribute))
			indices.append ((curr.ndx, curr.attribute))
			
			#Append the rest of the supporting points
			for i in range (len (strip)):
				curr = strip[i]
				indices.append ((curr.twin.prev.ndx, curr.twin.prev.attribute))
			
			#Store the strip, then restart the algorithm to get another strip.
			#We loop until the graph cannot be decomposed any further into strips
			strips.append (indices)
			
			#Print nice debugging information
			print ('\tStrip: {0} ({1} edge(s))'.format (len (indices), len (strip)))
		
		#Generate indices for the islands
		tri_indices = []
		for t in islands:
			edge = t.head
			while True:
				tri_indices.append ((edge.ndx, edge.attribute))
				edge = edge.next
				if edge is t.head:
					break
			
		#Compute some statistics
		sum = 0
		mem_strip = 0
		longest = -math.inf
		shortest = math.inf
		for s in strips:
			l = len (s)
			if l >= longest:
				longest = l
			if l <= shortest:
				shortest = l
			sum += l
			mem_strip += l
		
		avg = sum/len (strips)
		
		#Using 16 bit indices
		mem_strip *= 2
		mem_islands = 3*2*len (islands)
		mem_tris = 3*2*len (self.faces)
		
		print ('Statistics')
		print ('\tTotal strips: {0}'.format (len (strips)))
		print ('\tLongest run: {0} indices'.format (longest))
		print ('\tShortest run: {0} indices'.format (shortest))
		print ('\tAverage strip run: {0} indices'.format (avg))
		print ('\tNumber of islands: {0} tris'.format (len (islands)))
		print ('--Memory Usage--')
		print ('\tTristrip usage: {0} bytes ({1} kib)'.format (mem_strip, mem_strip/1024))
		print ('\tTriangles usage: {0} bytes ({1} kib)'.format (mem_tris, mem_tris/1024))
		print ('\tSavings: {0}%'.format (100 - 100*(mem_strip + mem_islands)/mem_tris))
		#Return the strips and islands
		return strips, tri_indices
	
#Generates a collision mesh from a graph
class Cpoly:
	def __init__ (self, loop, flags):
		self.loop = loop
		self.flags = flags

class Cmesh (Graph):
	def __init__ (self):
		super ().__init__ ()
		self.clipping = []
	
	def build (self):
		super ().build ()
		
		#TODO: merge polygons that share the same supporting plane
		#keep them either as triangles or quads.
		
		#Package up the resultant polygons
		pgons = []
		for p in self.faces:
			loop = []
			
			#Collect the indices into the loop array
			edge = p.head
			while True:
				loop.append (edge.ndx)
				
				edge = edge.next
				if edge is p.head:
					break
			
			#Canonise the edges by sorting the indices from least to greatest
			loop.sort ()
			
			#Add to the polygon list
			pgons.append (Cpoly (loop, 0))
		
		#Return polygons
		return pgons
	
