FROM python:3.9.6
# stvaranje direktorija
WORKDIR app/    
COPY requirements.txt req.txt 
#dependencies 
RUN pip install -r req.txt
COPY . . 
# koji port slusa 
EXPOSE 8080
CMD ["python3", "app.py"]

