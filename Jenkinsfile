pipeline {
    agent any

    environment {
        IMAGE_NAME     = "quantarisk-backend"
        CONTAINER_NAME = "quantarisk-backend"
        APP_PORT       = "8000"
    }

    stages {

        stage("Checkout") {
            steps {
                checkout scm
            }
        }

        stage("Lint") {
            steps {
                sh """
                    docker build -t quantarisk-lint -f Dockerfile .
                    docker run --rm \
                      -e PYTHONPATH=/app \
                      quantarisk-lint \
                      bash -c "pip install ruff mypy --quiet && ruff check app/ --select E,F,I --ignore E501 && mypy app/ --ignore-missing-imports --no-strict-optional || true"
                    docker rmi quantarisk-lint || true
                """
            }
        }

        stage("CI: Test") {
            steps {
                sh """
                    docker build -t quantarisk-test -f Dockerfile .
                    docker run --rm \
                      -e PYTHONPATH=/app \
                      quantarisk-test \
                      bash -c "pip install pytest-cov --quiet && pytest tests/ -v --ignore=tests/test_garch.py --tb=short --cov=app --cov-report=term-missing --cov-fail-under=75"
                    docker rmi quantarisk-test || true
                """
            }
        }

        stage("Docker Build") {
            steps {
                sh """
                    docker build \
                      --build-arg BUILD_VERSION=${BUILD_NUMBER} \
                      -t ${IMAGE_NAME}:${BUILD_NUMBER} \
                      -t ${IMAGE_NAME}:latest \
                      -f Dockerfile .
                    echo "Built ${IMAGE_NAME}:${BUILD_NUMBER}"
                """
            }
        }

        stage("Deploy") {
            steps {
                sh """
                    docker stop ${CONTAINER_NAME} || true
                    docker rm   ${CONTAINER_NAME} || true
                    DB_PATH=/var/jenkins_home/workspace/quantarisk-pipeline/quantarisk.db
                    touch $DB_PATH
                    docker run -d \
                      --name ${CONTAINER_NAME} \
                      -p ${APP_PORT}:8000 \
                      -v $DB_PATH:/app/quantarisk.db \
                      -e DATABASE_URL=sqlite:///./quantarisk.db \
                      -e PYTHONPATH=/app \
                      -e BUILD_VERSION=${BUILD_NUMBER} \
                      --restart unless-stopped \
                      ${IMAGE_NAME}:${BUILD_NUMBER}
                    echo "Waiting for container to start..."
                    sleep 15
                """
            }
        }

        stage("Smoke Tests") {
            steps {
                sh """
                    BASE="http://host.docker.internal:${APP_PORT}"

                    check() {
                        CODE=\$(curl -s -o /dev/null -w "%{http_code}" "\$1" 2>/dev/null || echo 000)
                        if [ "\$CODE" = "200" ]; then
                            echo "PASS [\$2]"
                        else
                            echo "FAIL [\$2] HTTP \$CODE"
                            exit 1
                        fi
                    }

                    check "\$BASE/api/health"                      "health"
                    check "\$BASE/api/symbols"                     "symbols"
                    check "\$BASE/api/symbols/search?q=A"          "symbols/search"
                    check "\$BASE/api/risk/overview"               "risk/overview"
                    check "\$BASE/api/risk/sectors"                "risk/sectors"
                    check "\$BASE/api/risk/correlation"            "risk/correlation"
                    check "\$BASE/api/risk/snapshot?symbol=AAPL"   "risk/snapshot"
                    check "\$BASE/api/risk/history?symbol=AAPL"    "risk/history"
                    check "\$BASE/api/risk/var?symbol=AAPL"        "risk/var"
                    check "\$BASE/api/drift/summary"               "drift/summary"
                    check "\$BASE/api/alerts"                      "alerts"
                    check "\$BASE/api/data-quality"                "data-quality"
                    check "\$BASE/api/predict?symbol=AAPL&days=10" "predict"

                    echo "All 13 smoke tests passed."
                """
            }
        }

    }

    post {
        success {
            echo "Pipeline SUCCESS - Build #${BUILD_NUMBER} deployed to port ${APP_PORT}"
        }
        failure {
            echo "Pipeline FAILED"
            sh """
                docker stop ${CONTAINER_NAME} || true
                docker rm   ${CONTAINER_NAME} || true
                docker run -d \
                  --name ${CONTAINER_NAME} \
                  -p ${APP_PORT}:8000 \
                  -e DATABASE_URL=sqlite:///./quantarisk.db \
                  -e PYTHONPATH=/app \
                  --restart unless-stopped \
                  ${IMAGE_NAME}:latest || true
            """
        }
        always {
            sh "docker rmi quantarisk-lint quantarisk-test || true"
        }
    }
}
