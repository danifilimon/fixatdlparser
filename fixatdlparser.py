# pyinstaller --onefile fixatdlparser.py

import sys
import re
import lxml.etree as etree
from loguru import logger

if (len(sys.argv) < 2) or (not sys.argv[1].endswith('xml')):
    logger.warning('Please pass a fixatdl file as a parameter')
    exit(0)

orig_file = sys.argv[1]
updated_file = 'updated_' + orig_file
to_remove = []
unsupported = ['.//{http://www.fixprotocol.org/FIXatdl-1-1/Validation}StrategyEdit',
               './/{http://www.fixprotocol.org/FIXatdl-1-1/Flow}StateRule',
               './/{http://www.fixprotocol.org/FIXatdl-1-1/Core}SecurityTypes',
               './/{http://www.fixprotocol.org/FIXatdl-1-1/Core}Description']
panel_path = './/{http://www.fixprotocol.org/FIXatdl-1-1/Layout}StrategyPanel'
parameter_path = './/{http://www.fixprotocol.org/FIXatdl-1-1/Core}Parameter'
param_type_path = '{http://www.w3.org/2001/XMLSchema-instance}type'
strategy_path = '{http://www.fixprotocol.org/FIXatdl-1-1/Core}Strategy'
control_path = './/{http://www.fixprotocol.org/FIXatdl-1-1/Layout}Control'
enumpair_path = './/{http://www.fixprotocol.org/FIXatdl-1-1/Core}EnumPair'
listitem_path = './/{http://www.fixprotocol.org/FIXatdl-1-1/Layout}ListItem'
layout_path = './/{http://www.fixprotocol.org/FIXatdl-1-1/Layout}StrategyLayout'
identifier_paths = [enumpair_path, listitem_path, parameter_path, control_path]
identifier_tags = ['enumID', 'name', 'ID', 'parameterRef']
layout_tags = ['StrategyLayout', 'StrategyPanel', 'Control', 'ListItem']
header = ('<Strategies xmlns="http://www.fixprotocol.org/FIXatdl-1-1/Core" xmlns:val="http://www.fixprotocol.org/'
          'FIXatdl-1-1/Validation" xmlns:lay="http://www.fixprotocol.org/FIXatdl-1-1/Layout" xmlns:flow="http://'
          'www.fixprotocol.org/FIXatdl-1-1/Flow" xmlns:tz="http://www.fixprotocol.org/FIXatdl-1-1/Timezones" '
          'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.fixprotocol.org/'
          'FIXatdl-1-1/Core fixatdl-core-1-1.xsd" strategyIdentifierTag="7620" versionIdentifierTag="7621">')

tree = etree.parse(orig_file)

# Get root node attributes
strategy_lbl = 'strategyIdentifierTag'
version_lbl = 'versionIdentifierTag'
strategy_tag = tree.getroot().get(strategy_lbl) if strategy_lbl in tree.getroot().attrib else '7620'
version_tag = tree.getroot().get(version_lbl) if version_lbl in tree.getroot().attrib else '7621'

# Remove unsupported nodes
for pattern in unsupported:
    for node in tree.findall(pattern):
        node.getparent().remove(node)

# Replace bad characters in identifiers: .- +
for path in identifier_paths:
    for node in tree.findall(path):
        for tag in identifier_tags:
            if tag in node.attrib:
                node.set(tag, re.sub('^([ \-+.()/])', '', node.get(tag)))
                node.set(tag, re.sub('([ \-+.()/])', '_', node.get(tag)))

# Remove {NULL} list items
for node in tree.findall(enumpair_path):
    if node.get('wireValue') == '{NULL}':
        enum_id = node.get('enumID')
        strategy = node.getparent().getparent()
        node.getparent().remove(node)
        for listitem in strategy.findall(listitem_path):
            if listitem.get('enumID') == enum_id:
                listitem.getparent().remove(listitem)
        for control in strategy.findall(control_path):
            if ('initValue' in control.attrib) and (control.get('initValue') == enum_id):
                control.attrib.pop('initValue')

# Remove ID attribute in Parameters
for node in tree.findall(parameter_path):
    if 'ID' in node.attrib:
        node.attrib.pop('ID')

# Remove use attribute in Control and initValue="blank"
for node in tree.findall(control_path):
    if 'use' in node.attrib:
        node.attrib.pop('use')
    if ('initValue' in node.attrib) and (node.get('initValue') == 'blank'):
        node.attrib.pop('initValue')

# Remove attributes from StrategyLayout and add namespace lay: to Control types
for node in tree.findall(layout_path):
    while len(node.attrib) > 1:
        node.attrib.pop()
    for control in node.findall(control_path):
        control.set(param_type_path, 'lay:' + control.get(param_type_path))
        if 'initValue' in control.attrib and control.get('initValue') == 'unchecked':
            control.set('initValue', 'false')
        if 'incrementPolicy' in control.attrib:
            control.set('increment', control.get('incrementPolicy'))
            control.attrib.pop('incrementPolicy')

# Replace True in StrategyPanel attributes
for node in tree.findall(panel_path):
    if ('collapsible' in node.attrib) and (node.get('collapsible') == 'True'):
        node.set('collapsible', 'true')

# Move minValue/maxValue from layout to parameters
for node in tree.findall(control_path):
    for tag in ['minValue', 'maxValue']:
        if tag in node.attrib:
            parameter_ref = node.get('parameterRef')
            value = node.get(tag)
            node.attrib.pop(tag)
            parameter = node.getparent()
            while parameter.tag != strategy_path:
                parameter = parameter.getparent()
            for param in parameter.findall(parameter_path):
                if param.get('name') == parameter_ref:
                    param.set(tag, value)

# Remove invalid initValue for CheckBox controls
for node in tree.findall(control_path):
    if node.get(param_type_path) == 'CheckBox_t' and node.get('initValue') not in ['true', 'false']:
        node.attrib.pop('initValue')

# Replace invalid border values on StrategyPanel
for node in tree.findall(panel_path):
    if re.match('One|one|none', node.get('border')):
        node.set('border', 'None')

# Change Char_t parameters with invalid values to String_t
par = tree.findall(parameter_path)[0]
for node in tree.findall(parameter_path):
    if node.get(param_type_path) == 'Char_t':
        for item in node.getchildren():
            if len(item.get('wireValue')) > 1:
                node.set(param_type_path, 'String_t')
                break

# Remove whitespace from elements
for node in tree.findall(control_path):
    if len(node.getchildren()) == 1:
        child = node.getchildren()[0]
        if child.attrib == {}:
            node.remove(child)
    if len(node.getchildren()) == 0:
        if node.attrib == {}:
            node.getparent().remove(node)
        else:
            parent = node.getparent()
            index = parent.getchildren().index(node)
            new = etree.SubElement(tree.getroot(), node.tag)
            for attr in node.attrib:
                new.set(attr, node.get(attr))
            parent.remove(node)
            parent.insert(index, new)

for node in tree.getroot().iter():
    if len(node.getchildren()) > 0:
        for elem in node.getchildren():
            if len(elem.getchildren()) == 0:
                if elem.attrib == {}:
                    to_remove.append(elem)

for elem in to_remove:
    elem.getparent().remove(elem)

tree.write(updated_file, pretty_print=True,  encoding='utf-8', xml_declaration=True)


# Read the file again to update layout nodes
file = open(updated_file)
text = list(file)
file.close()

for line in text:
    for pattern in layout_tags:
        if pattern in line:
            index = text.index(line)
            line = line.replace('<' + pattern, '<lay:' + pattern).replace('</' + pattern, '</lay:' + pattern)
            if pattern == 'StrategyLayout':
                line = line.replace(' xmlns="http://www.fixprotocol.org/FIXatdl-1-1/Layout"', '')
            text[index] = line

# Update header
for line in text[0:3]:
    if 'Strategies' in line:
        index = text.index(line)
        line = header.replace('7620', strategy_tag).replace('7621', version_tag)
        text[index] = line

# Write the file back with the updates
file = open(updated_file, 'w')
for line in text:
    file.write(line)
file.close()

logger.info('Updated file is ' + updated_file)
