import codecs
import os.path
import docutils.io

from sphinx.util.osutil import ensuredir, os_path
from ..writers.jupyter import JupyterWriter
from sphinx.builders import Builder
from sphinx.util.console import bold, darkgreen, brown
from sphinx.util.fileutil import copy_asset


class JupyterBuilder(Builder):
    """
    Builds Jupyter Notebook
    """
    name = "jupyter"
    format = "ipynb"
    out_suffix = ".ipynb"
    allow_parallel = True

    _writer_class = JupyterWriter

    def init(self):
        # Check default language is defined in the jupyter kernels
        def_lng = self.config["jupyter_default_lang"]
        if  def_lng not in self.config["jupyter_kernels"]:
            self.warn(
                "Default language defined in conf.py ({}) is not "
                "defined in the jupyter_kernels in conf.py. "
                "Set default language to python3"
                .format(def_lng))
            self.config["jupyter_default_lang"] = "python3"
        # If the user has overridden anything on the command line, set these things which have been overridden.
        instructions = []
        overrides = self.config['jupyter_options']
        if overrides:
            instructions = overrides.split(",")

        for instruction in instructions:
            if instruction:
                if instruction == 'code_only':
                    self.config["jupyter_conversion_mode"] = "code"
                else:
                    # Fail on unrecognised command.
                    self.warn("Unrecognise command line parameter " + instruction + ", ignoring.")

    def get_outdated_docs(self):
        for docname in self.env.found_docs:
            if docname not in self.env.all_docs:
                yield docname
                continue
            targetname = self.env.doc2path(docname, self.outdir,
                                           self.out_suffix)
            try:
                targetmtime = os.path.getmtime(targetname)
            except OSError:
                targetmtime = 0
            try:
                srcmtime = os.path.getmtime(self.env.doc2path(docname))
                if srcmtime > targetmtime:
                    yield docname
            except EnvironmentError:
                pass

    def get_target_uri(self, docname, typ=None):
        return docname

    def prepare_writing(self, docnames):
        self.writer = self._writer_class(self)

    def get_doc_context(self, docname, body, metatags):
        # type: (unicode, unicode, Dict) -> Dict[unicode, Any]
        # taken from sphinx/builders/html
        """Collect items for the template context of a page."""
        # find out relations
        prev = next = None
        parents = []
        rellinks = self.globalcontext['rellinks'][:]
        related = self.relations.get(docname)
        titles = self.env.titles
        if related and related[2]:
            try:
                next = {
                    'link': self.get_relative_uri(docname, related[2]),
                    'title': self.render_partial(titles[related[2]])['title']
                }
                rellinks.append((related[2], next['title'], 'N', _('next')))
            except KeyError:
                next = None
        if related and related[1]:
            try:
                prev = {
                    'link': self.get_relative_uri(docname, related[1]),
                    'title': self.render_partial(titles[related[1]])['title']
                }
                rellinks.append(
                    (related[1], prev['title'], 'P', _('previous')))
            except KeyError:
                # the relation is (somehow) not in the TOC tree, handle
                # that gracefully
                prev = None
        while related and related[0]:
            try:
                parents.append(
                    {'link': self.get_relative_uri(docname, related[0]),
                     'title': self.render_partial(titles[related[0]])['title']})
            except KeyError:
                pass
            related = self.relations.get(related[0])
        if parents:
            # remove link to the master file; we have a generic
            # "back to index" link already
            parents.pop()
        parents.reverse()

        # title rendered as HTML
        title = self.env.longtitles.get(docname)
        title = title and self.render_partial(title)['title'] or ''

        # Suffix for the document
        source_suffix = path.splitext(self.env.doc2path(docname))[1]

        # the name for the copied source
        if self.config.html_copy_source:
            sourcename = docname + source_suffix
            if source_suffix != self.config.html_sourcelink_suffix:
                sourcename += self.config.html_sourcelink_suffix
        else:
            sourcename = ''

        # metadata for the document
        meta = self.env.metadata.get(docname)

        # local TOC and global TOC tree
        self_toc = TocTree(self.env).get_toc_for(docname, self)
        toc = self.render_partial(self_toc)['fragment']

        return {
            'parents': parents,
            'prev': prev,
            'next': next,
            'title': title,
            'meta': meta,
            'body': body,
            'metatags': metatags,
            'rellinks': rellinks,
            'sourcename': sourcename,
            'toc': toc,
            # only display a TOC if there's more than one item to show
            'display_toc': (self.env.toc_num_entries[docname] > 1),
            'page_source_suffix': source_suffix,
        }

    def write_doc(self, docname, doctree):
        # work around multiple string % tuple issues in docutils;
        # replace tuples in attribute values with lists
        doctree = doctree.deepcopy()
        destination = docutils.io.StringOutput(encoding="utf-8")
        self.writer.write(doctree, destination)
        outfilename = os.path.join(self.outdir, os_path(docname) + self.out_suffix)

        # mkdir if the directory does not exist
        ensuredir(os.path.dirname(outfilename))

        try:
            with codecs.open(outfilename, "w", "utf-8") as f:
                f.write(self.writer.output)
        except (IOError, OSError) as err:
            self.warn("error writing file %s: %s" % (outfilename, err))

    def copy_static_files(self):
        # copy all static files
        self.info(bold("copying static files... "), nonl=True)
        ensuredir(os.path.join(self.outdir, '_static'))

        # excluded = Matcher(self.config.exclude_patterns + ["**/.*"])
        for static_path in self.config["jupyter_static_file_path"]:
            entry = os.path.join(self.confdir, static_path)
            if not os.path.exists(entry):
                self.warn(
                    "jupyter_static_path entry {} does not exist"
                    .format(entry))
            else:
                copy_asset(entry, os.path.join(self.outdir, "_static"))
        self.info("done")

    def finish(self):
        self.finish_tasks.add_task(self.copy_static_files)
