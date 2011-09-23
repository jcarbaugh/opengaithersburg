# Open Gaithersburg

An experiment in open data published by the city of Gaithersburg, MD.

<http://opengaithersburg.org>

This project is [open source.](https://github.com/jcarbaugh/opengaithersburg)

## Run Open Gaithersburg locally

1. Install the required Python packages found in *requirements.txt*.
1. Visit <http://campaignfinancing.gaithersburgmd.gov/> and download all data sets to the *data* directory.
1. Run *python load.py* to load, process, clean, and geocode the data.
1. Run *python og.py* to run the web app.
1. Visit <http://localhost:8000>

## TODO

* Generate static JSON dumps of campaign profiles from which the pages will be generated. No more messy database calls!
* Add expenditure data
* Then add loan and obligation data

