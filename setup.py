from setuptools import find_packages, setup

setup(
    name='basebot',
    version='0.1.0',    
    description='A tradingbot base template to interact with the tradingbot22 backend',
    url='https://github.com/JustinGuese/tradingbot22-tradingbots',
    author='Justin Güse',
    author_email='guese.justin@gmail.com',
    license='BSD 2-clause',
    install_requires=['requests',
                    'tqdm',
                    'pandas',
                    'scipy',
                    'sklearn'                  
                    ],
    classifiers = [
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir = {"": "basebot22"},
    packages = find_packages(where="basebot22"),
    python_requires = ">=3.6"
)
