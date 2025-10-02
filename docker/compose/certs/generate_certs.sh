#!/bin/bash
##
## Certificate Generation Script for MQTT Cluster with mTLS
## Creates CA, server, and client certificates for production use
##

set -e

CERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CA_KEY="${CERT_DIR}/ca.key"
CA_CERT="${CERT_DIR}/ca.crt"
SERVER_KEY="${CERT_DIR}/server.key"
SERVER_CSR="${CERT_DIR}/server.csr"
SERVER_CERT="${CERT_DIR}/server.crt"
SERVER_PEM="${CERT_DIR}/server.pem"

# Certificate validity (in days)
CA_VALIDITY=3650  # 10 years for CA
CERT_VALIDITY=365 # 1 year for server/client certs

echo "=== MQTT Cluster Certificate Generation ==="
echo "Certificate directory: ${CERT_DIR}"
echo

# Create directory if it doesn't exist
mkdir -p "${CERT_DIR}"

##
## Step 1: Generate CA (Certificate Authority)
##
echo "[1/5] Generating Certificate Authority (CA)..."
if [ -f "${CA_CERT}" ]; then
    echo "CA certificate already exists. Skipping..."
else
    # Generate CA private key
    openssl genrsa -out "${CA_KEY}" 4096

    # Generate CA certificate
    openssl req -new -x509 -days ${CA_VALIDITY} -key "${CA_KEY}" -out "${CA_CERT}" \
        -subj "/C=US/ST=State/L=City/O=OEE-Manufacturing/OU=IT/CN=OEE-MQTT-CA" \
        -addext "keyUsage = critical, digitalSignature, keyCertSign, cRLSign" \
        -addext "basicConstraints = critical, CA:TRUE"

    echo "CA certificate created: ${CA_CERT}"
fi
echo

##
## Step 2: Generate Server Certificate (for EMQX brokers)
##
echo "[2/5] Generating Server Certificate..."
if [ -f "${SERVER_CERT}" ]; then
    echo "Server certificate already exists. Skipping..."
else
    # Generate server private key
    openssl genrsa -out "${SERVER_KEY}" 2048

    # Create OpenSSL config for SAN (Subject Alternative Names)
    cat > "${CERT_DIR}/server.cnf" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = req_ext

[dn]
C = US
ST = State
L = City
O = OEE-Manufacturing
OU = MQTT-Cluster
CN = mqtt.oee.local

[req_ext]
subjectAltName = @alt_names

[alt_names]
DNS.1 = mqtt.oee.local
DNS.2 = emqx1.local
DNS.3 = emqx2.local
DNS.4 = emqx3.local
DNS.5 = localhost
IP.1 = 127.0.0.1
IP.2 = 172.20.0.2
IP.3 = 172.20.0.3
IP.4 = 172.20.0.4
EOF

    # Generate server CSR
    openssl req -new -key "${SERVER_KEY}" -out "${SERVER_CSR}" -config "${CERT_DIR}/server.cnf"

    # Sign server certificate with CA
    openssl x509 -req -in "${SERVER_CSR}" -CA "${CA_CERT}" -CAkey "${CA_KEY}" -CAcreateserial \
        -out "${SERVER_CERT}" -days ${CERT_VALIDITY} -sha256 \
        -extfile "${CERT_DIR}/server.cnf" -extensions req_ext

    # Create PEM file for HAProxy (cert + key)
    cat "${SERVER_CERT}" "${SERVER_KEY}" > "${SERVER_PEM}"

    echo "Server certificate created: ${SERVER_CERT}"
    echo "Server PEM created: ${SERVER_PEM}"
fi
echo

##
## Step 3: Generate Edge Client Certificate Template Function
##
echo "[3/5] Creating edge client certificate generation function..."

generate_client_cert() {
    local CLIENT_NAME=$1
    local CLIENT_KEY="${CERT_DIR}/client_${CLIENT_NAME}.key"
    local CLIENT_CSR="${CERT_DIR}/client_${CLIENT_NAME}.csr"
    local CLIENT_CERT="${CERT_DIR}/client_${CLIENT_NAME}.crt"

    if [ -f "${CLIENT_CERT}" ]; then
        echo "Client certificate for ${CLIENT_NAME} already exists."
        return 0
    fi

    # Generate client private key
    openssl genrsa -out "${CLIENT_KEY}" 2048

    # Generate client CSR
    openssl req -new -key "${CLIENT_KEY}" -out "${CLIENT_CSR}" \
        -subj "/C=US/ST=State/L=City/O=OEE-Manufacturing/OU=Edge-Gateways/CN=${CLIENT_NAME}"

    # Sign client certificate with CA
    openssl x509 -req -in "${CLIENT_CSR}" -CA "${CA_CERT}" -CAkey "${CA_KEY}" -CAcreateserial \
        -out "${CLIENT_CERT}" -days ${CERT_VALIDITY} -sha256 \
        -extfile <(echo "extendedKeyUsage = clientAuth")

    echo "Client certificate created for: ${CLIENT_NAME}"
    echo "  Certificate: ${CLIENT_CERT}"
    echo "  Private Key: ${CLIENT_KEY}"
}

# Export the function for use in other scripts
export -f generate_client_cert

echo "Client certificate generation function created."
echo "Usage: generate_client_cert <client_name>"
echo

##
## Step 4: Generate Sample Edge Client Certificates
##
echo "[4/5] Generating sample edge client certificates..."
generate_client_cert "edge_SITE01-LINE01"
generate_client_cert "edge_SITE01-LINE02"
generate_client_cert "analytics_OEE-PROCESSOR"
echo

##
## Step 5: Set Permissions
##
echo "[5/5] Setting certificate permissions..."
chmod 600 "${CA_KEY}" "${SERVER_KEY}" "${CERT_DIR}"/client_*.key 2>/dev/null || true
chmod 644 "${CA_CERT}" "${SERVER_CERT}" "${CERT_DIR}"/client_*.crt 2>/dev/null || true
echo

##
## Summary
##
echo "=== Certificate Generation Complete ==="
echo
echo "CA Certificate:     ${CA_CERT}"
echo "Server Certificate: ${SERVER_CERT}"
echo "Server PEM:         ${SERVER_PEM}"
echo
echo "Client certificates created:"
ls -1 "${CERT_DIR}"/client_*.crt 2>/dev/null || echo "  (none yet)"
echo
echo "To generate additional client certificates, run:"
echo "  source ${BASH_SOURCE[0]}"
echo "  generate_client_cert edge_YOUR-NODE-ID"
echo
echo "Certificate validity:"
echo "  CA:     ${CA_VALIDITY} days"
echo "  Certs:  ${CERT_VALIDITY} days"
echo
echo "IMPORTANT: Distribute client certificates securely to edge devices."
echo "           Keep private keys confidential!"
echo
