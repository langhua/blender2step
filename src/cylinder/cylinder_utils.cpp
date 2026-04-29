// Cylinder Utility Functions - Helper utilities for cylinder detection
#include "../include/step_exporter_internal.h"
#include "cylinder_types.h"
#include <cmath>
#include <algorithm>
#include <vector>

// 辅助函数：计算容差
double tol_for(double value) {
    return std::max(fabs(value) * 0.01, 0.01);
}

// 辅助函数：计算包围盒对角线
double compute_bounding_diagonal(const std::vector<std::vector<double>>& vertices) {
    if (vertices.empty()) return 1000;
    
    double xmn=1e20, ymn=1e20, zmn=1e20, xmx=-1e20, ymx=-1e20, zmx=-1e20;
    for (const auto& v : vertices) {
        if (v.size() >= 3) {
            xmn = std::min(xmn, v[0]); ymn = std::min(ymn, v[1]); zmn = std::min(zmn, v[2]);
            xmx = std::max(xmx, v[0]); ymx = std::max(ymx, v[1]); zmx = std::max(zmx, v[2]);
        }
    }
    return sqrt(pow(xmx-xmn,2)+pow(ymx-ymn,2)+pow(zmx-zmn,2));
}
