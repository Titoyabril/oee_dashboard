import subprocess
import sys
import os

# Try to convert using Blender's Python API if Blender is installed
blend_file = r"C:\dev\projects\oee_dashboard\oee_dashboard\static\models\uploads_files_2578050_spidey.blend"
output_file = r"C:\dev\projects\oee_dashboard\oee_dashboard\static\models\spidey.gltf"

# Create a Blender Python script to do the conversion
blender_script = '''
import bpy
import sys

blend_file = sys.argv[-2]
output_file = sys.argv[-1]

# Clear existing mesh
bpy.ops.wm.read_factory_settings(use_empty=True)

# Load the blend file
bpy.ops.wm.open_mainfile(filepath=blend_file)

# Export as GLTF
bpy.ops.export_scene.gltf(filepath=output_file, export_format='GLTF_SEPARATE')
'''

# Try to find Blender executable
blender_paths = [
    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.5\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.4\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.3\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender\blender.exe",
    r"C:\Program Files (x86)\Blender Foundation\Blender\blender.exe",
    "blender"  # Try system PATH
]

blender_exe = None
for path in blender_paths:
    if os.path.exists(path) or path == "blender":
        blender_exe = path
        break

if blender_exe:
    print(f"Found Blender at: {blender_exe}")
    # Save the script to a temporary file
    script_file = "temp_convert.py"
    with open(script_file, 'w') as f:
        f.write(blender_script)
    
    # Run Blender in background mode
    cmd = [blender_exe, "--background", "--python", script_file, "--", blend_file, output_file]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.returncode == 0:
            print(f"Successfully converted to {output_file}")
        else:
            print(f"Error: {result.stderr}")
    except Exception as e:
        print(f"Failed to run Blender: {e}")
    finally:
        # Clean up temp script
        if os.path.exists(script_file):
            os.remove(script_file)
else:
    print("Blender not found. Please install Blender or provide the path.")