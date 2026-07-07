// ── Curved (cosine) path: solid loft with embedded bottom fillet ──
    if (curved) {
        double hw = width / 2.0, hd = depth / 2.0;
        double total_inset = std::min(hw, hd) * curve_ratio * 0.5;
        double hh = total_h / 2.0;
        int nLayers = 10;
        int bfSegs = (bottom_fillet > 0.001) ? 6 : 0;
        double bf = bottom_fillet;

        // Build layers bottom→top: fillet zone then cosine wall
        auto buildLayers = [&](double base_hw, double base_hd, double base_cr,
                                double z_shift) {
            std::vector<double> zs, hws, hds;

            // 1. Bottom fillet zone: z from -hh+z_shift to -hh+z_shift+bf
            if (bf > 0.001) {
                for (int i = 0; i <= bfSegs; i++) {
                    double z = -hh + z_shift + bf * i / bfSegs;
                    double s = (double)i / bfSegs;
                    // Blender: offset = bf * (1 - sin(pi/2 * s))
                    double offset = bf * (1.0 - sin(M_PI / 2.0 * s));
                    // Cosine inset at the wall bottom (z = -hh+z_shift+bf)
                    double t_wall = (hh - (-hh + z_shift + bf)) / (2.0 * hh);
                    t_wall = std::max(0.0, std::min(1.0, t_wall));
                    double wall_inset = total_inset * (1.0 - cos(M_PI / 2.0 * t_wall));
                    zs.push_back(z);
                    hws.push_back(base_hw - wall_inset - offset);
                    hds.push_back(base_hd - wall_inset - offset);
                }
            }

            // 2. Cosine wall: z from -hh+z_shift+bf to +hh+z_shift
            double wall_bot = -hh + z_shift + bf;
            double wall_top = hh + z_shift;
            int start_i = (bf > 0.001) ? 1 : 0;  // skip duplicate at wall_bot
            for (int i = start_i; i <= nLayers; i++) {
                double z = wall_bot + (wall_top - wall_bot) * i / nLayers;
                double t = (hh - (z - z_shift)) / (2.0 * hh);
                t = std::max(0.0, std::min(1.0, t));
                double inset = total_inset * (1.0 - cos(M_PI / 2.0 * t));
                zs.push_back(z);
                hws.push_back(base_hw - inset);
                hds.push_back(base_hd - inset);
            }
            return std::make_tuple(zs, hws, hds);
        };

        // Helper: create closed solid via ThruSections (solid mode, smooth)
        auto makeSolid = [&](const std::vector<double>& hw_arr,
                             const std::vector<double>& hd_arr,
                             const std::vector<double>& z_arr,
                             double cr_val) -> TopoDS_Solid {
            BRepOffsetAPI_ThruSections loft(true, false, 1e-6);
            for (size_t i = 0; i < hw_arr.size(); i++) {
                TopoDS_Wire w = create_rounded_rect_wire(
                    hw_arr[i] * 2.0, hd_arr[i] * 2.0, cr_val, z_arr[i], 0.0);
                if (w.IsNull()) return TopoDS_Solid();
                loft.AddWire(w);
            }
            loft.Build();
            if (!loft.IsDone()) return TopoDS_Solid();
            TopoDS_Shape s = loft.Shape();
            return s.ShapeType() == TopAbs_SOLID ? TopoDS::Solid(s) : TopoDS_Solid();
        };

        // Outer solid (z_shift = 0)
        auto [oz, ohw, ohd] = buildLayers(hw, hd, cr, 0.0);
        TopoDS_Solid outerSolid = makeSolid(ohw, ohd, oz, cr);
        if (outerSolid.IsNull()) return TopoDS_Shape();

        // Inner solid: z_shift = thickness
        double iw = hw - thickness, id_ = hd - thickness;
        double icr = std::min(cr, std::min(iw, id_) - 0.01);
        if (icr < 0.01) icr = 0.01;
        auto [iz, ihw, ihd] = buildLayers(iw, id_, icr, thickness);
        TopoDS_Solid innerSolid = makeSolid(ihw, ihd, iz, icr);
        if (innerSolid.IsNull()) return TopoDS_Shape();

        // Boolean: outer - inner → shell
        BRepAlgoAPI_Cut cut(outerSolid, innerSolid);
        if (!cut.IsDone()) return TopoDS_Shape();
        TopoDS_Shape result = cut.Shape();

        // Merge faces for cleaner output
        ShapeUpgrade_UnifySameDomain unifier(result, true, true, true);
        unifier.Build();
        result = unifier.Shape();

        // Shift to Z=0
        gp_Trsf shiftUp;
        shiftUp.SetTranslation(gp_Vec(0, 0, hh));
        result = BRepBuilderAPI_Transform(result, shiftUp).Shape();
        return result;
    }
