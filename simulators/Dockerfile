FROM python:3.11-slim

LABEL maintainer="OEE Dashboard Team"
LABEL description="Allen-Bradley ControlLogix PLC Simulator"

WORKDIR /app

# Copy simulator files
COPY controllogix_simulator.py .
COPY plc_server.py .

# Install any required dependencies (minimal for simulator)
RUN pip install --no-cache-dir --upgrade pip

# Expose PLC simulator port (CIP/EtherNet-IP default is 44818)
EXPOSE 44818

# Run the simulator server
CMD ["python", "plc_server.py"]
