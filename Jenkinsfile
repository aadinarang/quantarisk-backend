/*
 * QuantaRisk CI/CD/CT Pipeline — Blue/Green Deployment
 *
 * Stages:
 *  1. Checkout + Lint      ruff + mypy static analysis
 *  2. CI: Test             pytest --cov, threshold >= 80%
 *  3. Docker Build & Tag   build + tag :BUILD_NUMBER and :latest
 *  4. Deploy to Green      start new version in inactive slot, health-check loop
 *  5. CT: Smoke Tests      validate all 13 endpoints on green container
 *  6. Traffic Switch       nginx upstream reload (zero-downtime handover)
 *  7. Post                 success notification / conditional rollback on failure
 */

pipeline {
    agent any

    environment {
        IMAGE_NAME   = "quantarisk-backend"
        BLUE_PORT    = "8001"
        GREEN_PORT   = "8002"
        NGINX_CONF   = "/etc/nginx/conf.d/quantarisk.conf"
        DB_PATH      = "/opt/quantarisk/quantarisk.db"
        MODELS_PATH  = "/opt/quantarisk/models"
    }

    stages {

        stage('Checkout + Lint') {
            steps {
                checkout scm
                sh '''
                    pip install ruff mypy --quiet
                    echo "=== ruff ==="
                    ruff check app/ --select E,F,I --ignore E501
                    echo "=== mypy ==="
                    mypy app/ --ignore-missing-imports --no-strict-optional || true
                '''
            }
        }

        stage('CI: Test') {
            steps {
                sh '''
                    docker build -t ${IMAGE_NAME}-test -f Dockerfile .
                    docker run --rm \
                      -e PYTHONPATH=/app \
                      -e DATABASE_URL=sqlite:///./test.db \
                      -e BUILD_VERSION=${BUILD_NUMBER} \
                      ${IMAGE_NAME}-test \
                      bash -c "pytest tests/ -v --tb=short --cov=app --cov-report=xml:coverage.xml --cov-report=term-missing --cov-fail-under=80"
                '''
            }
        }

        stage('Docker Build & Tag') {
            steps {
                sh '''
                    docker build \
                      --build-arg BUILD_VERSION=${BUILD_NUMBER} \
                      -t ${IMAGE_NAME}:${BUILD_NUMBER} \
                      -t ${IMAGE_NAME}:latest \
                      -f Dockerfile .
                    echo "Built ${IMAGE_NAME}:${BUILD_NUMBER}"
                '''
            }
        }

        stage('Deploy to Green') {
            steps {
                script {
                    def activePort = sh(
                        script: "grep -o '800[12]' ${NGINX_CONF} 2>/dev/null | head -1 || echo '8001'",
                        returnStdout: true
                    ).trim()
                    env.ACTIVE_SLOT   = (activePort == "8001") ? "blue"  : "green"
                    env.INACTIVE_SLOT = (activePort == "8001") ? "green" : "blue"
                    env.INACTIVE_PORT = (activePort == "8001") ? env.GREEN_PORT : env.BLUE_PORT
                    echo "Active: ${env.ACTIVE_SLOT}:${activePort}  →  Deploying to: ${env.INACTIVE_SLOT}:${env.INACTIVE_PORT}"
                }
                sh '''
                    docker stop quantarisk-${INACTIVE_SLOT} 2>/dev/null || true
                    docker rm   quantarisk-${INACTIVE_SLOT} 2>/dev/null || true

                    docker run -d \
                      --name quantarisk-${INACTIVE_SLOT} \
                      -p ${INACTIVE_PORT}:8000 \
                      -e DATABASE_URL=sqlite:////data/quantarisk.db \
                      -e PYTHONPATH=/app \
                      -e BUILD_VERSION=${BUILD_NUMBER} \
                      -e MODELS_DIR=/models \
                      -v ${DB_PATH}:/data/quantarisk.db \
                      -v ${MODELS_PATH}:/models \
                      --network quantarisk-net \
                      ${IMAGE_NAME}:${BUILD_NUMBER}

                    echo "Waiting for health check on port ${INACTIVE_PORT}..."
                    ATTEMPTS=0
                    until [ $ATTEMPTS -ge 30 ]; do
                        STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:${INACTIVE_PORT}/api/health 2>/dev/null || echo 000)
                        if [ "$STATUS" = "200" ]; then
                            echo "Container healthy after $ATTEMPTS attempts"
                            exit 0
                        fi
                        ATTEMPTS=$((ATTEMPTS + 1))
                        sleep 2
                    done
                    echo "Health check timed out"
                    exit 1
                '''
            }
        }

        stage('CT: Smoke Tests') {
            steps {
                sh '''
                    BASE="http://127.0.0.1:${INACTIVE_PORT}"

                    run_check() {
                        CODE=$(curl -s -o /tmp/ct_last.json -w "%{http_code}" "$1" 2>/dev/null)
                        if [ "$CODE" != "200" ]; then
                            echo "FAIL [$2] HTTP $CODE"
                            exit 1
                        fi
                        echo "PASS [$2]"
                    }

                    run_check "$BASE/api/health"                     "health"
                    run_check "$BASE/api/symbols"                    "symbols"
                    run_check "$BASE/api/symbols/search?q=a"         "symbols/search"
                    run_check "$BASE/api/risk/overview"              "risk/overview"
                    run_check "$BASE/api/risk/sectors"               "risk/sectors"
                    run_check "$BASE/api/risk/correlation"           "risk/correlation"
                    run_check "$BASE/api/drift/summary"              "drift/summary"
                    run_check "$BASE/api/data-quality"               "data-quality"
                    run_check "$BASE/api/alerts"                     "alerts"

                    SYMBOL=$(curl -s "$BASE/api/symbols" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['symbol'] if d else 'AAPL')")
                    echo "Detail checks for symbol: $SYMBOL"

                    run_check "$BASE/api/risk/snapshot?symbol=$SYMBOL"   "risk/snapshot"
                    run_check "$BASE/api/risk/history?symbol=$SYMBOL"    "risk/history"
                    run_check "$BASE/api/risk/var?symbol=$SYMBOL"        "risk/var"
                    run_check "$BASE/api/ratios?symbol=$SYMBOL"          "ratios"
                    run_check "$BASE/api/predict?symbol=$SYMBOL&days=10" "predict"

                    python3 - <<PYEOF
import json, sys

# Health checks
d = json.load(open("/tmp/ct_last.json"))
# (last call was predict — check its shape)
assert "forecastPrices" in d, "missing forecastPrices"
assert len(d["forecastPrices"]) == 10, f"expected 10 prices, got {len(d['forecastPrices'])}"
assert d["modelVersion"] in ("math-v1", "lstm-v1"), "unknown modelVersion"
assert all(p > 0 for p in d["forecastPrices"]), "forecast prices must be positive"
print("PASS [predict shape]")
PYEOF

                    python3 - <<PYEOF
import json
d = json.load(open("/tmp/ct_last.json"))
# Correlation diagonal check
import urllib.request
resp = urllib.request.urlopen("${BASE}/api/risk/correlation")
c = json.loads(resp.read())
for i in range(len(c["matrix"])):
    assert abs(c["matrix"][i][i] - 1.0) < 0.01, f"diagonal[{i}] not 1.0"
print("PASS [correlation diagonal]")
PYEOF

                    echo "All CT smoke tests passed."
                '''
            }
        }

        stage('Traffic Switch') {
            steps {
                sh '''
                    echo "Switching nginx upstream to ${INACTIVE_SLOT} on port ${INACTIVE_PORT}"
                    cat > ${NGINX_CONF} <<CONF
upstream quantarisk_backend {
    server 127.0.0.1:${INACTIVE_PORT};
}
CONF
                    nginx -s reload
                    echo "Nginx reloaded — traffic now routing to quantarisk-${INACTIVE_SLOT}"
                    docker stop quantarisk-${ACTIVE_SLOT} 2>/dev/null || true
                    echo "Old container quantarisk-${ACTIVE_SLOT} stopped (kept for instant rollback)"
                '''
            }
        }
    }

    post {
        success {
            echo "Pipeline SUCCESS — Build #${BUILD_NUMBER} deployed to slot: ${env.INACTIVE_SLOT}"
        }
        failure {
            script {
                echo "Pipeline FAILED — checking whether rollback is required"
                if (env.INACTIVE_PORT) {
                    sh """
                        CURRENT=\$(grep -o '800[12]' ${NGINX_CONF} 2>/dev/null | head -1 || echo '')
                        if [ "\$CURRENT" = "${env.INACTIVE_PORT}" ]; then
                            echo "Traffic was switched — rolling back to ${env.ACTIVE_SLOT}"
                            ROLLBACK_PORT=\$([ "${env.ACTIVE_SLOT}" = "blue" ] && echo "${BLUE_PORT}" || echo "${GREEN_PORT}")
                            sed -i "s/${env.INACTIVE_PORT}/\$ROLLBACK_PORT/" ${NGINX_CONF}
                            nginx -s reload
                            docker start quantarisk-${env.ACTIVE_SLOT} 2>/dev/null || true
                            docker stop  quantarisk-${env.INACTIVE_SLOT} 2>/dev/null || true
                            echo "Rollback complete"
                        else
                            echo "Traffic not switched — old container still active, no rollback needed"
                            docker stop quantarisk-${env.INACTIVE_SLOT} 2>/dev/null || true
                        fi
                    """
                }
            }
        }
    }
}
