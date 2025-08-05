from django.shortcuts import render

def dashboard(request):
    return render(request, 'oee_analytics/dashboard.html')
