import sys
import Part
import FreeCAD as App
import FreeCADGui as Gui

path = r"F:\git\blender2step\step_exporter\test30.step"
shape = Part.read(path)
solids = shape.Solids

doc = App.newDocument("Import")
obj = doc.addObject("Part::Feature", "All")
obj.Shape = shape
doc.recompute()

Gui.showMainWindow()
view = Gui.ActiveDocument.ActiveView
view.viewIsometric()
view.fitAll()
view.saveImage(r"F:\git\blender2step\_r_iso2.png", 1600, 1200, "White", "White")
print("saved iso")
