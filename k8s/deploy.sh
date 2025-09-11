#!/bin/bash

echo "🚀 Deploying AMR Engine to Kubernetes..."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed or not in PATH"
    exit 1
fi

# Check if cluster is reachable
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Kubernetes cluster is not reachable"
    exit 1
fi

echo "✅ Kubernetes cluster is accessible"

# Create namespace first
echo "📦 Creating namespace..."
kubectl apply -f namespace.yaml

# Apply ConfigMaps
echo "⚙️  Creating ConfigMaps..."
kubectl apply -f configmap.yaml
kubectl apply -f rules-configmap.yaml

# Deploy the application
echo "🚀 Deploying AMR Engine..."
kubectl apply -f deployment.yaml

# Create services
echo "🔗 Creating services..."
kubectl apply -f service.yaml

# Create ingress (optional)
echo "🌐 Creating ingress..."
kubectl apply -f ingress.yaml

echo "⏳ Waiting for deployment to be ready..."
kubectl rollout status deployment/amr-engine -n amr-engine --timeout=300s

# Display deployment status
echo ""
echo "📊 Deployment Status:"
kubectl get pods -n amr-engine -l app=amr-engine
kubectl get services -n amr-engine
kubectl get ingress -n amr-engine

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📝 Access methods:"
echo "   NodePort: http://localhost:30080"
echo "   Port-forward: kubectl port-forward -n amr-engine service/amr-engine-service 8080:80"
echo "   Ingress: http://amr-engine.local (if ingress controller is installed)"
echo ""
echo "🔍 Useful commands:"
echo "   View logs: kubectl logs -n amr-engine -l app=amr-engine"
echo "   Scale deployment: kubectl scale -n amr-engine deployment/amr-engine --replicas=3"
echo "   Delete deployment: kubectl delete namespace amr-engine"