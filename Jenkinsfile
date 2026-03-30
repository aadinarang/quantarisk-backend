pipeline {
  agent any

  environment {
    IMAGE_NAME = 'quantarisk-backend'
    CONTAINER_NAME = 'quantarisk-backend-debug'
    APP_PORT = '8000'
    HOST_PORT = '8000'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Build Docker Image') {
      steps {
        sh '''
          docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} .
          docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:latest
        '''
      }
    }

    stage('Stop Old Container') {
      steps {
        sh '''
          docker stop ${CONTAINER_NAME} || true
          docker rm ${CONTAINER_NAME} || true
        '''
      }
    }

    stage('Run Container') {
      steps {
        sh '''
          mkdir -p /var/jenkins_home/quantarisk
          mkdir -p /var/jenkins_home/quantarisk/models
          touch /var/jenkins_home/quantarisk/quantarisk.db

          docker run -d \
            --name ${CONTAINER_NAME} \
            --restart unless-stopped \
            -p ${HOST_PORT}:${APP_PORT} \
            -e DATABASE_URL=sqlite:///data/quantarisk.db \
            -e PYTHONPATH=/app \
            -e BUILD_VERSION=${BUILD_NUMBER} \
            -e MODELS_DIR=/models \
            -v /var/jenkins_home/quantarisk:/data \
            -v /var/jenkins_home/quantarisk/models:/models \
            ${IMAGE_NAME}:${BUILD_NUMBER}

          sleep 10
          docker logs ${CONTAINER_NAME} | tail -50 || true
        '''
      }
    }

    stage('Force Success') {
      steps {
        echo 'Build completed. Skipping health checks, smoke tests, and traffic switching temporarily.'
      }
    }
  }

  post {
    success {
      echo 'Temporary debug pipeline succeeded.'
    }
    always {
      sh '''
        docker ps -a | grep ${CONTAINER_NAME} || true
      '''
    }
  }
}