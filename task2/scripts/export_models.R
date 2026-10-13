# Export the PETRIMED models that pass its quality filter to xgboost JSON, for Python.
#
#   Rscript task2/scripts/export_models.R
#
# For each method (psbo, mags, metab) and size fraction (pico, nano), keeps the models of each PST
# with a validation correlation of at least MIN_COR, as PETRIMED's figure scripts do, and writes
# task2/data/models/<method>_<fraction>/<PST>.jsonl, one model per line, and a summary.csv.
# Needs the xgboost package (install.packages("xgboost")); the models were saved with xgboost >= 2.

suppressMessages(library(xgboost))
MIN_COR <- 0.6
dir_in <- "task2/PETRIMED/MODELS"
dir_out <- "task2/data/models"

summary <- data.frame()
for (method in c("psbo", "mags", "metab")) {
  for (fraction in c("pico", "nano")) {
    prefix <- file.path(dir_in, paste0(method, "_", fraction))
    models <- readRDS(paste0(prefix, "_models.RData"))
    info <- readRDS(paste0(prefix, "_models_info.RData"))
    out <- file.path(dir_out, paste0(method, "_", fraction))
    dir.create(out, recursive = TRUE, showWarnings = FALSE)
    for (pst in names(models)) {
      if (!is.data.frame(info[[pst]])) next
      keep <- !is.na(info[[pst]]$cor_valid) & info[[pst]]$cor_valid >= MIN_COR
      if (!any(keep)) next
      ids <- info[[pst]]$model_id[keep]
      json <- vapply(models[[pst]][ids], function(b) rawToChar(xgb.save.raw(b, raw_format = "json")), "")
      writeLines(json, file.path(out, paste0(pst, ".jsonl")))
      summary <- rbind(summary, data.frame(method = method, fraction = fraction, pst = pst, models = sum(keep),
                                           cor_valid = mean(info[[pst]]$cor_valid[keep])))
    }
  }
}
write.csv(summary, file.path(dir_out, "summary.csv"), row.names = FALSE)
print(summary, digits = 2)
