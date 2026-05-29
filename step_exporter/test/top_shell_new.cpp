TopoDS_Shape create_top_shell_filleted_solid(
    double width, double depth, double outer_height,
    double top_thickness, double wall_thickness,
    double corner_radius,
    double outer_fillet_radius, double inner_fillet_radius,
    double top_recess, double top_offset_y,
    double window_len, double window_wid)
{
    std::cout << "[STEP Exporter] Creating top shell: " << width << "x" << depth
              << " h=" << outer_height << " top_t=" << top_thickness
              << " wall=" << wall_thickness << " cr=" << corner_radius
              << " outer_f=" << outer_fillet_radius << " inner_f=" << inner_fillet_radius
              << " recess=" << top_recess << " topYOff=" << top_offset_y << std::endl;

    double hh = outer_height / 2.0;
    double hw = width / 2.0;
    double hd = depth / 2.0;

    // Clamp fillet radii
    double max_safe_fillet = std::min(outer_height * 0.25, std::min(width, depth) * 0.05);
    outer_fillet_radius = std::min(outer_fillet_radius, max_safe_fillet);
    inner_fillet_radius = std::min(inner_fillet_radius, max_safe_fillet * 0.8);
    if (inner_fillet_radius < 0.1) inner_fillet_radius = 0.1;

    // === Step 1: Create rounded box (same approach as bottom shell) ===
    TopoDS_Shape outerBox = create_rounded_box_solid(width, depth, outer_height, corner_radius);
    if (outerBox.IsNull()) {
        std::cerr << "[STEP Exporter] Failed to create outer rounded box" << std::endl;
        return TopoDS_Shape();
    }

    TopoDS_Shape taperedSolid;
    if (outerBox.ShapeType() == TopAbs_SOLID) {
        taperedSolid = TopoDS::Solid(outerBox);
    } else {
        taperedSolid = ensure_solid(outerBox);
        if (taperedSolid.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to convert box to solid" << std::endl;
            return TopoDS_Shape();
        }
    }
    {int fc=0; for(TopExp_Explorer e(taperedSolid,TopAbs_FACE);e.More();e.Next())fc++; std::cout<<"[STEP Exporter] Rounded box faces: "<<fc<<std::endl;}

    // === Step 2: Apply outer bottom fillet FIRST (before taper cutting) ===
    if (outer_fillet_radius > 0.001) {
        try {
            BRepFilletAPI_MakeFillet filletMaker(TopoDS::Solid(taperedSolid));
            int filletCount = 0;
            for (TopExp_Explorer exp(taperedSolid, TopAbs_EDGE); exp.More(); exp.Next()) {
                TopoDS_Edge edge = TopoDS::Edge(exp.Current());
                BRepAdaptor_Curve curve(edge);
                gp_Pnt p1 = curve.Value(curve.FirstParameter());
                gp_Pnt p2 = curve.Value(curve.LastParameter());
                if (fabs(p1.Z() + hh) < 0.5 && fabs(p2.Z() + hh) < 0.5) {
                    filletMaker.Add(outer_fillet_radius, edge);
                    filletCount++;
                }
            }
            if (filletCount > 0) {
                filletMaker.Build();
                if (filletMaker.IsDone()) {
                    taperedSolid = filletMaker.Shape();
                    std::cout << "[STEP Exporter] Outer bottom fillet: " << filletCount << " edges, r=" << outer_fillet_radius << std::endl;
                }
            }
        } catch (...) {}
    }

    // === Step 3: Taper sides using half-space Common cuts ===
    if (top_recess > 0.001) {
        double top_hw = hw - top_recess;
        double top_hd = hd - top_recess;
        double top_cy = -top_offset_y;

        struct TaperDef { char axis; double botVal; double topVal; };
        TaperDef tapers[] = {
            {'X',  hw,  top_hw},
            {'X', -hw, -top_hw},
            {'Y',  hd,  top_hd + top_cy},
            {'Y', -hd, -top_hd + top_cy}
        };

        for (int i = 0; i < 4; i++) {
            char axis = tapers[i].axis;
            double botVal = tapers[i].botVal;
            double topVal = tapers[i].topVal;

            if (fabs(botVal - topVal) < 0.001) continue;

            double botX = (axis == 'X') ? botVal : 0;
            double botY = (axis == 'Y') ? botVal : 0;
            double topX = (axis == 'X') ? topVal : 0;
            double topY = (axis == 'Y') ? topVal : 0;

            // Plane defined by points: bottom-edge (botX,botY,-hh) and top-edge (topX,topY,+hh)
            // Direction along the edge from bottom to top
            gp_Vec edgeDir(topX - botX, topY - botY, outer_height);
            // Horizontal direction for the cut plane (perpendicular to taper direction)
            gp_Vec horizDir = (axis == 'X') ? gp_Vec(0, 1, 0) : gp_Vec(1, 0, 0);
            // Normal = edgeDir cross horizDir gives plane normal
            gp_Vec planeNormal = edgeDir.Crossed(horizDir);

            if (planeNormal.Magnitude() < Precision::Confusion()) continue;

            gp_Dir normalDir(planeNormal);
            // The smaller botVal means inside; normal should point outward
            // For +X side: botVal > topVal, so the plane tilts INWARD
            // The normal computed should point outward
            // If planeNormal points toward the side we're clipping FROM, that's correct
            // Check: for +X side, edgeDir = (top_hw - hw, 0, outer_height) which goes INWARD
            //      horizDir = (0, 1, 0)
            //      planeNormal = edgeDir x horizDir = (0, 0, outer_height*(top_hw-hw)) - (..., 0, ...) 
            //      = (0*0 - outer_height*1, outer_height*0 - (top_hw-hw)*0, (top_hw-hw)*1 - 0*0)
            //      = (-outer_height, 0, top_hw - hw)
            // So for +X: normal.X = -outer_height (points left), that's outward from the right side
            // Good.

            // Build a large face on the taper plane for the half-space
            gp_Ax3 taperAx3(gp_Pnt(botX, botY, -hh), normalDir);
            // Create a large rectangular face
            double faceSize = std::max(width, depth) * 3;
            BRepBuilderAPI_MakeFace mf(gp_Pln(taperAx3), -faceSize, faceSize, -faceSize, faceSize);
            if (!mf.IsDone()) {
                std::cerr << "[STEP Exporter] Face creation " << i << " failed" << std::endl;
                continue;
            }

            // Reference point on the INSIDE of the taper plane
            // The center of the bottom is always inside
            gp_Pnt refPnt(0, -top_offset_y * 0.5, -hh);
            BRepPrimAPI_MakeHalfSpace halfSpace(mf.Face(), refPnt);
            if (!halfSpace.IsDone()) {
                std::cerr << "[STEP Exporter] Half-space " << i << " failed" << std::endl;
                continue;
            }

            BRepAlgoAPI_Common commonOp(taperedSolid, halfSpace.Solid());
            if (!commonOp.IsDone()) {
                std::cerr << "[STEP Exporter] Common (taper) " << i << " failed" << std::endl;
                continue;
            }

            taperedSolid = commonOp.Shape();
            if (taperedSolid.IsNull()) {
                std::cerr << "[STEP Exporter] Taper " << i << " produced null solid" << std::endl;
                return TopoDS_Shape();
            }
            std::cout << "[STEP Exporter] Taper " << i << " applied (" << axis << ": " << botVal << "->" << topVal << ")" << std::endl;
        }
    }

    if (taperedSolid.IsNull()) return TopoDS_Shape();

    // === Step 4: Hollow by Boolean Cut (same as perfect bottom shell) ===
    if (wall_thickness > 0.001) {
        double inner_w = width - 2.0 * wall_thickness;
        double inner_d = depth - 2.0 * wall_thickness;
        double inner_h = outer_height - top_thickness + 0.1;
        double inner_cr = std::max(0.0, corner_radius - wall_thickness);

        if (inner_w > 0 && inner_d > 0 && inner_h > 0) {
            TopoDS_Shape innerBox = create_rounded_box_solid(inner_w, inner_d, inner_h, inner_cr);
            if (!innerBox.IsNull()) {
                TopoDS_Solid innerSolid;
                if (innerBox.ShapeType() == TopAbs_SOLID) {
                    innerSolid = TopoDS::Solid(innerBox);
                } else {
                    innerSolid = ensure_solid(innerBox);
                }

                if (!innerSolid.IsNull()) {
                    double inner_z_shift = -hh + top_thickness + 0.05;
                    gp_Trsf innerTrsf;
                    innerTrsf.SetTranslation(gp_Vec(0, -top_offset_y * 0.5, inner_z_shift));
                    TopLoc_Location innerLoc(innerTrsf);
                    innerSolid.Move(innerLoc);

                    BRepAlgoAPI_Cut cutMaker(TopoDS::Solid(taperedSolid), innerSolid);
                    if (cutMaker.IsDone()) {
                        taperedSolid = cutMaker.Shape();
                        std::cout << "[STEP Exporter] Boolean cut (hollow) succeeded" << std::endl;
                    } else {
                        std::cerr << "[STEP Exporter] Boolean cut (hollow) failed" << std::endl;
                    }
                }
            }
        }
    }

    if (taperedSolid.IsNull()) return TopoDS_Shape();

    // === Step 5: Apply inner bottom fillet ===
    if (inner_fillet_radius > 0.001 && taperedSolid.ShapeType() == TopAbs_SOLID) {
        try {
            BRepFilletAPI_MakeFillet filletMaker(TopoDS::Solid(taperedSolid));
            int filletCount = 0;
            double innerFloorZ = -hh + top_thickness;
            for (TopExp_Explorer exp(taperedSolid, TopAbs_EDGE); exp.More(); exp.Next()) {
                TopoDS_Edge edge = TopoDS::Edge(exp.Current());
                BRepAdaptor_Curve curve(edge);
                gp_Pnt p1 = curve.Value(curve.FirstParameter());
                gp_Pnt p2 = curve.Value(curve.LastParameter());
                bool isHorizontal = fabs(p1.Z() - p2.Z()) < Precision::Confusion();
                bool isAtFloor = fabs(p1.Z() - innerFloorZ) < 1.0;
                if (isHorizontal && isAtFloor) {
                    filletMaker.Add(inner_fillet_radius, edge);
                    filletCount++;
                }
            }
            if (filletCount > 0) {
                filletMaker.Build();
                if (filletMaker.IsDone()) {
                    taperedSolid = filletMaker.Shape();
                    std::cout << "[STEP Exporter] Inner fillet: " << filletCount << " edges" << std::endl;
                }
            }
        } catch (...) {}
    }

    // === Step 6: Fix shape ===
    taperedSolid = fix_shape_enhanced(taperedSolid, 0.001);

    // === Step 7: Cut window ===
    if (window_len > 0.0 && window_wid > 0.0) {
        double topZ = hh - top_thickness;
        double topY_center = -top_offset_y;
        BRepPrimAPI_MakeBox windowMaker(
            gp_Pnt(-window_len/2.0, topY_center - window_wid/2.0, topZ - top_thickness - 2.0),
            window_len, window_wid, top_thickness + 6.0);
        BRepAlgoAPI_Cut wc(taperedSolid, windowMaker.Solid());
        if (wc.IsDone()) {
            taperedSolid = wc.Shape();
            std::cout << "[STEP Exporter] Window cut: " << window_len << "x" << window_wid << std::endl;
        }
    }

    // === Step 8: Final validation ===
    taperedSolid = ensure_solid(taperedSolid);
    if (taperedSolid.IsNull()) return TopoDS_Shape();

    BRepCheck_Analyzer analyzer(TopoDS::Solid(taperedSolid));
    if (!analyzer.IsValid()) {
        taperedSolid = fix_shape_enhanced(taperedSolid, 0.001);
        taperedSolid = ensure_solid(taperedSolid);
    }

    int fc = 0;
    for (TopExp_Explorer exp(taperedSolid, TopAbs_FACE); exp.More(); exp.Next()) fc++;
    std::cout << "[STEP Exporter] Final: " << fc << " faces, "
              << (BRepCheck_Analyzer(TopoDS::Solid(taperedSolid)).IsValid() ? "valid" : "invalid") << std::endl;
    if (taperedSolid.ShapeType() == TopAbs_SOLID) {
        GProp_GProps props;
        BRepGProp::VolumeProperties(taperedSolid, props);
        std::cout << "[STEP Exporter] Volume: " << props.Mass() << " mm^3" << std::endl;
    }
    return taperedSolid;
}