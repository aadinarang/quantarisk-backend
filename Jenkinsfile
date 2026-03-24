pipeline {
    agent any

    environment {
        IMAGE_NAME = 'quantarisk-backend'
        CONTAINER_NAME = 'quantarisk-backend'
    }

    stages {

        stage('Checkout') {
            steps {
                echo 'Checking out code from GitHub...'
                checkout scm
            }
        }

        stage('Run Tests') {
            steps {
                echo 'Running tests inside Docker...'
                sh '''
                    docker run --rm \
                      -v $(pwd):/app \
                      -w /app \
                      -e PYTHONPATH=/app \
                      -e DATABASE_URL=sqlite:///./quantarisk.db \
                      python:3.11-slim \
                      sh -c "pip install -r requirements.txt -q && pytest tests/ -v --tb=short"
                '''
            }
        }

        stage('Docker Build') {
            steps {
                echo 'Building Docker image...'
                sh 'docker build -t quantarisk-backend .'
            }
        }

        stage('Deploy') {
            steps {
                echo 'Deploying with docker-compose...'
                sh 'docker-compose down || true'
                sh 'docker-compose up -d'
            }
        }

    }

    post {
        success {
            echo 'Pipeline completed successfully. QuantaRisk is live.'
        }
        failure {
            echo 'Pipeline failed. Check the logs above for errors.'
        }
    }
}
