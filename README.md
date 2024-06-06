# SUN-DIC

Stellenbosch University DIC Code

# Important Notice

You are accessing a very early release of the Stellenbosch University DIC Code called SUN-DIC. Currently this code has the following key features and limitations. Please forward any problems and/or suggestions for improvement to the author. More detailed information about the implementation will be provided at a later stage.

## Limitations

1. Can currently only deal with 2D planar problems (a stereo version is planned)
2. Can currently only deal with a single image pair (that is a total of two images). Future work will allow for an incremental or absolute strategy to deal with multiple image pairs
3. Can only specify a rectangular region of interest (ROI), but an all black background in the image pair can be used to deal with irregularly shaped domains
4. There are currently no GUI available for the code

## Key features

1. Completely open source using standard Python libraries wherever possible
2. Make use of the zero-mean normalized sum of squared differences (ZNSSD) correlation criterion
3. Have an advanced starting strategy for automatically creating initial guesses at a small number of starting points using the Akaze feature detection algorithm
4. Have both linear (affine) and quadratic shape functions are available
5. Have both an inverse compositional Gauss-Newton (IC-GN) and an inverse compositional Levenberg-Marquardt (IC-LM) solver implemented
6. Calculate both displacements and strains
7. Strains are calculated using a Savitzky-Golay smoothing operations

# Installation

1. Clone the repository
2. Create a virtual environment
3. Activate the virtual environment
4. Install the required packages contained in the `requirements.txt` file
   Below are some pointers how to achieve this using either python/pip or anacoda

## Using `pip`

1. Create a new virtual environment - this could be done from the main directory of the cloned repository

```
python3 -m venv venv
```

2. Activate the virtual environment (from Linux)

```
source venv/bin/activate
```

3. Install the requirements

```
pip install -r requirements.txt
```

## Using `anacoda` - from the command line

1. Create a new virtual environment - this could be done from the main directory of the cloned repository

```
conda create -n venv pip
```

2. Activate the virtual environment

```
conda activate venv
```

3. Install the requirements

```
pip install -r requirements.txt
```

# Usage

1. Open the `test_sundic.ipynb` Jupyter Notebook for a detailed and complete working example
2. Open this from the main SUN-DIC directory and be sure to use the virtual environment you created above
3. Note that the general work flow is to modify the `setting.ini` file, perform the DIC analysis and finally to post-process the results

# Acknowledgementss

- The SUN-DIC analysis code is based on work done by Ed Brisley as part of his MEng degree at Stellenbosch University. His MEng thesis is available at the Stellenbosch University library (https://scholar.sun.ac.za/items/7a519bf5-e62b-45cb-82f1-11f4969da23a)
- The interpolator used is `fast_interp` written by David Stein and available under the Apache 2.0 license at: https://github.com/dbstein/fast_interp
- The Savitsky-Golay 2D smoothing algorithm is from the scipy cookbook available at: https://scipy-cookbook.readthedocs.io/items/SavitzkyGolay.html

# License

This project is licensed under the MIT License - see the LICENSE.md file for details

# Authors

- Gerhard Venter
