try:
    import sphinx_rtd_theme
except ImportError:
    sphinx_rtd_theme = None

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'deSEC DNS API'
project_copyright = '%Y, deSEC e.V., Individual Contributors'
author = 'deSEC e.V., Individual Contributors'


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.duration',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'default'
if sphinx_rtd_theme:
    html_theme = 'sphinx_rtd_theme'

html_static_path = ['_static']


# -- Options for LaTeX output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-latex-output

latex_documents = [
    ('index', 'deSEC.tex', 'deSEC DNS API Documentation', 'deSEC e.V., Individual Contributors', 'manual'),
]
