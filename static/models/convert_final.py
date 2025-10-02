import subprocess
import os

# Paths
blend_file = r"C:\dev\projects\oee_dashboard\oee_dashboard\static\models\uploads_files_2578050_spidey.blend"
output_file = r"C:\dev\projects\oee_dashboard\oee_dashboard\static\models\spidey.gltf"
blender_exe = r"C:\dev\projects\oee_dashboard\oee_dashboard\static\models\blender-4.2.3-windows-x64\blender.exe"

# Blender Python script for conversion
script_content = '''
import bpy
import sys

# Clear the default scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Get the blend file path from command line arguments  
blend_file = sys.argv[sys.argv.index("--") + 1]
output_file = sys.argv[sys.argv.index("--") + 2]

print(f"Loading: {blend_file}")
print(f"Output: {output_file}")

# Load the blend file
bpy.ops.wm.open_mainfile(filepath=blend_file)

# Export as GLTF
bpy.ops.export_scene.gltf(
    filepath=output_file,
    export_format='GLTF_SEPARATE',
    export_selected=False,
    export_extras=True,
    export_cameras=False,
    export_lights=False
)

print("Conversion completed!")
'''

# Write the script to a file
script_file = r"C:\dev\projects\oee_dashboard\oee_dashboard\static\models\convert_script.py"
with open(script_file, 'w') as f:
    f.write(script_content)

print(f"Blender executable: {blender_exe}")
print(f"Blender exists: {os.path.exists(blender_exe)}")

# Run Blender conversion
cmd = [
    blender_exe, 
    "--background", 
    "--python", script_file,
    "--", blend_file, output_file
]

print(f"Running command: {' '.join(cmd)}")

try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)
    print(f"Return code: {result.returncode}")
    
    if os.path.exists(output_file):
        print(f"SUCCESS! GLTF file created: {output_file}")
        print(f"File size: {os.path.getsize(output_file)} bytes")
    else:
        print("GLTF file was not created")
        
except subprocess.TimeoutExpired:
    print("Conversion timed out")
except Exception as e:
    print(f"Error running Blender: {e}")

# Clean up
if os.path.exists(script_file):
    os.remove(script_file)