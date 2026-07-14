# Ordered experiment index

| No. | Directory | Stage / status |
|---:|---|---|
| 01 | `01-2片双极板接触Abaqus接触分析` | Initial two-plate contact workflow |
| 02 | `02-15片双极板堆叠Abaqus接触分析` | Initial 15-plate stack |
| 03 | `03-15片双极板自然顺序Abaqus接触分析` | Natural-order comparison |
| 04 | `04-15片双极板最小距离和顺序含端板Abaqus接触分析` | Minimum-distance order with endplates |
| 05 | `05-15片双极板自然顺序含端板Abaqus接触分析` | Natural order with endplates |
| 06 | `06-15片双极板最小距离和顺序刚体端板Abaqus接触分析` | Minimum order with rigid endplates |
| 07 | `07-15片双极板最大距离和顺序刚体端板Abaqus接触分析` | Maximum order with rigid endplates |
| 08 | `08-15片双极板三种排序等效柔性层压力均匀性分析` | Equivalent flexible-layer exploration |
| 09 | `09-15片双极板三种排序刚体端板低接触刚度Abaqus接触分析` | Low contact-stiffness sensitivity |
| 10 | `10-15片双极板三种排序Abaqus等效柔性弹簧层分析` | Equivalent spring-layer exploration |
| 11 | `11-15片双极板三种排序Abaqus双节点弹簧层分析` | Two-node spring-layer exploration |
| 12 | `12-15片双极板三种排序Abaqus桁架柔性层分析` | Truss flexible-layer exploration |
| 13 | `13-15片双极板三种排序真实接触释放弯曲Abaqus分析` | True-contact bending release |
| 14 | `14-15片双极板三种排序真实面面接触刚体端板Abaqus分析` | True surface contact and rigid endplates |
| 15 | `15-15片双极板三种排序真实面面接触位移控制Abaqus分析` | Completed displacement-control reference |
| 16 | `16-15片双极板三种排序真实面面接触低刚度材料Abaqus分析` | Low-modulus sensitivity |
| 17 | `17-15片双极板三种排序真实面面接触小压缩位移Abaqus分析` | Small-compression sensitivity |
| 18 | `18-15片双极板三种排序真实面面接触高弯曲刚度Abaqus分析` | High bending-stiffness sensitivity |
| 19 | `19-15片双极板三种排序真实面面接触压力控制低刚度少约束Abaqus分析` | Standard pressure control; incomplete convergence |
| 20 | `20-15片双极板三种排序真实面面接触压力控制中低刚度少约束Abaqus分析` | Standard pressure control; incomplete convergence |
| 21 | `21-15片双极板三种排序真实面面接触自定义压力少约束Abaqus分析` | 0.448 MPa Standard attempt; incomplete convergence |
| 22 | `22-15片双极板三种排序Abaqus显式准静态压力控制少约束分析` | Initial Explicit attempt; soft-material instability |
| 23 | `23-15片双极板三种排序Abaqus显式阻尼准静态压力控制分析` | Damped Explicit attempt; shell folding instability |
| 24 | `24-15片双极板三种排序Abaqus显式真实刚度准静态压力控制分析` | Completed, but dynamic energy remained high |
| 25 | `25-15片双极板三种排序Abaqus显式恒压阻尼准静态接触分析` | Quasi-static, but S4R artificial energy was high |
| 26 | `26-15片双极板三种排序Abaqus显式全积分壳恒压接触分析` | Validated full-integration frictionless reference |
| 27 | `27-15片双极板三种排序Abaqus显式摩擦耦合恒压接触分析` | Finite-sliding friction rejected due distortion/energy |
| 28 | `28-15片双极板三种排序Abaqus显式小滑移摩擦恒压接触分析` | Validated small-sliding friction reference |
| 29 | `29-15片低压高刚度角点定位三排序Abaqus参数实验` | Completed; min order best, natural/max mixed by metric |
| 30 | `30-24片合成曲面中压三点定位三排序Abaqus参数实验` | Completed; strongest strict min-natural-max trend so far |
| 31 | `31-30片合成曲面中高压双锚点三排序Abaqus参数实验` | Prepared for distributed run; not yet executed |
| 32 | `32-45片合成曲面高泊松比四角定位三排序Abaqus参数实验` | Prepared for distributed run; not yet executed |
| 33 | `33-60片合成曲面高压高刚度边缘导向三排序Abaqus参数实验` | Prepared for distributed run; not yet executed |
| 34 | `34-15片双极板精确算法三排序Abaqus显式小滑移摩擦恒压接触分析` | Completed; exact DP restores strict trend, but old exp28 min remains better |

The status labels describe the latest known interpretation of each experiment. Solver outputs are deliberately not part of this scripts repository.
