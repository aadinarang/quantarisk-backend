pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                    docker build -t quantarisk-test -f Dockerfile .
                    docker run --rm \
                      -e PYTHONPATH=/app \
                      -e DATABASE_URL=sqlite:///./quantarisk.db \
                      quantarisk-test \
                      bash -c "pytest tests/ -v --tb=short"
                '''
            }
        }

        stage('Docker Build') {
            steps {
                sh 'docker build -t quantarisk-backend .'
            }
        }

        stage('Deploy') {
            steps {
                sh 'docker-compose down || true'
                sh 'docker-compose up -d'
            }
        }

    }

    post {
        success {
            echo 'Pipeline completed. QuantaRisk is live.'
        }
        failure {
            echo 'Pipeline failed. Check logs above.'
        }
    }
}
