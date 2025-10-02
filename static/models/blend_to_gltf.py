import trimesh
import os

# File paths
blend_file = r"C:\dev\projects\oee_dashboard\oee_dashboard\static\models\uploads_files_2578050_spidey.blend"
output_file = r"C:\dev\projects\oee_dashboard\oee_dashboard\static\models\spidey.gltf"

print(f"Attempting to load: {blend_file}")
print(f"File exists: {os.path.exists(blend_file)}")

try:
    # Try to load the blend file with trimesh
    print("Loading blend file with trimesh...")
    mesh = trimesh.load(blend_file)
    
    print(f"Loaded mesh type: {type(mesh)}")
    
    # Export as GLTF
    print(f"Exporting to: {output_file}")
    mesh.export(output_file)
    
    print("Successfully converted blend to GLTF!")
    
except Exception as e:
    print(f"Trimesh failed: {e}")
    
    # Try alternative approach
    try:
        print("Trying alternative method...")
        import bpy
        print("Blender Python API found - this shouldn't happen in this context")
    except ImportError:
        print("Blender Python API not available")
        
    # Try reading as generic 3D file
    try:
        print("Trying to read as generic file...")
        with open(blend_file, 'rb') as f:
            data = f.read(100)  # Read first 100 bytes
            print(f"File header: {data[:20]}")
    except Exception as read_error:
        print(f"Could not read file: {read_error}")